import json
import os
from datetime import datetime
from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, String, Integer, DateTime, Float
from sqlalchemy.orm import declarative_base, sessionmaker, Session
import boto3

DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")

AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
LOW_SEAT_LAMBDA_NAME = os.getenv("LOW_SEAT_LAMBDA_NAME", "low-seat-notification")

DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()

lambda_client = boto3.client("lambda", region_name=AWS_REGION)

app = FastAPI(title="Registration Service")


class EventORM(Base):
    __tablename__ = "events"

    event_id = Column(String, primary_key=True, index=True)
    title = Column(String, nullable=False)
    venue = Column(String, nullable=False)
    date_time = Column(String, nullable=False)
    ticket_price = Column(Float, nullable=False)
    capacity = Column(Integer, nullable=False)
    seats_available = Column(Integer, nullable=False)


class RegistrationORM(Base):
    __tablename__ = "registrations"

    registration_id = Column(String, primary_key=True, index=True)
    event_id = Column(String, nullable=False)
    name = Column(String, nullable=False)
    email = Column(String, nullable=False)
    ticket_count = Column(Integer, nullable=False)
    timestamp = Column(DateTime, nullable=False)


class Registration(BaseModel):
    registration_id: str
    event_id: str
    name: str
    email: str
    ticket_count: int


Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def registration_to_dict(registration: RegistrationORM):
    return {
        "registration_id": registration.registration_id,
        "event_id": registration.event_id,
        "name": registration.name,
        "email": registration.email,
        "ticket_count": registration.ticket_count,
        "timestamp": registration.timestamp.isoformat(),
    }


def invoke_low_seat_lambda(event_id: str, remaining_seats: int):
    payload = {
        "event_id": event_id,
        "remaining_seats": remaining_seats,
        "timestamp": datetime.utcnow().isoformat()
    }

    response = lambda_client.invoke(
        FunctionName=LOW_SEAT_LAMBDA_NAME,
        InvocationType="Event",
        Payload=json.dumps(payload).encode("utf-8")
    )

    return {
        "lambda_invoked": True,
        "status_code": response.get("StatusCode")
    }


@app.get("/")
def health_check():
    return {"service": "registration-service", "status": "running"}


@app.post("/registrations")
def create_registration(registration: Registration, db: Session = Depends(get_db)):
    if registration.ticket_count <= 0:
        raise HTTPException(status_code=400, detail="Ticket count must be greater than zero")

    existing_registration = db.query(RegistrationORM).filter(
        RegistrationORM.registration_id == registration.registration_id
    ).first()

    if existing_registration:
        raise HTTPException(status_code=400, detail="Registration already exists")

    event = db.query(EventORM).filter(EventORM.event_id == registration.event_id).first()

    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    if event.seats_available < registration.ticket_count:
        raise HTTPException(status_code=400, detail="Not enough seats available")

    event.seats_available = event.seats_available - registration.ticket_count

    new_registration = RegistrationORM(
        registration_id=registration.registration_id,
        event_id=registration.event_id,
        name=registration.name,
        email=registration.email,
        ticket_count=registration.ticket_count,
        timestamp=datetime.utcnow(),
    )

    db.add(new_registration)
    db.commit()
    db.refresh(new_registration)

    lambda_result = None
    low_seat_alert = event.seats_available < 10

    if low_seat_alert:
        lambda_result = invoke_low_seat_lambda(
            event_id=event.event_id,
            remaining_seats=event.seats_available
        )

    return {
        "message": "Registration saved successfully",
        "registration": registration_to_dict(new_registration),
        "remaining_seats": event.seats_available,
        "low_seat_alert": low_seat_alert,
        "lambda_result": lambda_result
    }


@app.get("/registrations")
def get_registrations(db: Session = Depends(get_db)):
    registrations = db.query(RegistrationORM).all()
    return [registration_to_dict(registration) for registration in registrations]


@app.get("/registrations/{registration_id}")
def get_registration(registration_id: str, db: Session = Depends(get_db)):
    registration = db.query(RegistrationORM).filter(
        RegistrationORM.registration_id == registration_id
    ).first()

    if not registration:
        raise HTTPException(status_code=404, detail="Registration not found")

    return registration_to_dict(registration)