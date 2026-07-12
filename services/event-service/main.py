import os
from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, String, Float, Integer
from sqlalchemy.orm import declarative_base, sessionmaker, Session

DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")

DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()

app = FastAPI(title="Event Service")


class EventORM(Base):
    __tablename__ = "events"

    event_id = Column(String, primary_key=True, index=True)
    title = Column(String, nullable=False)
    venue = Column(String, nullable=False)
    date_time = Column(String, nullable=False)
    ticket_price = Column(Float, nullable=False)
    capacity = Column(Integer, nullable=False)
    seats_available = Column(Integer, nullable=False)


class Event(BaseModel):
    event_id: str
    title: str
    venue: str
    date_time: str
    ticket_price: float
    capacity: int
    seats_available: int


Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def event_to_dict(event: EventORM):
    return {
        "event_id": event.event_id,
        "title": event.title,
        "venue": event.venue,
        "date_time": event.date_time,
        "ticket_price": event.ticket_price,
        "capacity": event.capacity,
        "seats_available": event.seats_available,
    }


@app.get("/")
def health_check():
    return {"service": "event-service", "status": "running"}


@app.post("/events")
def create_event(event: Event, db: Session = Depends(get_db)):
    existing_event = db.query(EventORM).filter(EventORM.event_id == event.event_id).first()

    if existing_event:
        raise HTTPException(status_code=400, detail="Event already exists")

    new_event = EventORM(**event.dict())
    db.add(new_event)
    db.commit()
    db.refresh(new_event)

    return {"message": "Event created successfully", "event": event_to_dict(new_event)}


@app.get("/events")
def get_events(db: Session = Depends(get_db)):
    events = db.query(EventORM).all()
    return [event_to_dict(event) for event in events]


@app.get("/events/{event_id}")
def get_event(event_id: str, db: Session = Depends(get_db)):
    event = db.query(EventORM).filter(EventORM.event_id == event_id).first()

    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    return event_to_dict(event)


@app.put("/events/{event_id}/seats")
def update_seats(event_id: str, seats_available: int, db: Session = Depends(get_db)):
    event = db.query(EventORM).filter(EventORM.event_id == event_id).first()

    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    event.seats_available = seats_available
    db.commit()
    db.refresh(event)

    return {
        "message": "Seats updated",
        "event_id": event_id,
        "seats_available": event.seats_available,
        "low_seat_alert": event.seats_available < 10,
    }
