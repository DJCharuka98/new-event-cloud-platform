import os
from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, String
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

app = FastAPI(title="Program Service")


class ProgramORM(Base):
    __tablename__ = "programs"

    program_id = Column(String, primary_key=True, index=True)
    event_id = Column(String, nullable=False)
    day = Column(String, nullable=False)
    track = Column(String, nullable=False)
    session = Column(String, nullable=False)
    speaker_name = Column(String, nullable=False)
    start_time = Column(String, nullable=False)
    end_time = Column(String, nullable=False)


class Program(BaseModel):
    program_id: str
    event_id: str
    day: str
    track: str
    session: str
    speaker_name: str
    start_time: str
    end_time: str


Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def program_to_dict(program: ProgramORM):
    return {
        "program_id": program.program_id,
        "event_id": program.event_id,
        "day": program.day,
        "track": program.track,
        "session": program.session,
        "speaker_name": program.speaker_name,
        "start_time": program.start_time,
        "end_time": program.end_time,
    }


@app.get("/")
def health_check():
    return {"service": "program-service", "status": "running"}


@app.post("/programs")
def create_program(program: Program, db: Session = Depends(get_db)):
    existing_program = db.query(ProgramORM).filter(ProgramORM.program_id == program.program_id).first()

    if existing_program:
        raise HTTPException(status_code=400, detail="Program already exists")

    new_program = ProgramORM(**program.dict())
    db.add(new_program)
    db.commit()
    db.refresh(new_program)

    return {"message": "Program created successfully", "program": program_to_dict(new_program)}


@app.get("/programs")
def get_programs(db: Session = Depends(get_db)):
    programs = db.query(ProgramORM).all()
    return [program_to_dict(program) for program in programs]


@app.get("/programs/{program_id}")
def get_program(program_id: str, db: Session = Depends(get_db)):
    program = db.query(ProgramORM).filter(ProgramORM.program_id == program_id).first()

    if not program:
        raise HTTPException(status_code=404, detail="Program not found")

    return program_to_dict(program)
