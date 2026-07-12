import json
import os
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict

import clickhouse_connect
from fastapi import FastAPI
from pydantic import BaseModel, Field

CLICKHOUSE_HOST = os.getenv("CLICKHOUSE_HOST", "clickhouse")
CLICKHOUSE_PORT = int(os.getenv("CLICKHOUSE_PORT", "8123"))
CLICKHOUSE_DATABASE = os.getenv("CLICKHOUSE_DATABASE", "default")
CLICKHOUSE_USER = os.getenv("CLICKHOUSE_USER", "default")
CLICKHOUSE_PASSWORD = os.getenv("CLICKHOUSE_PASSWORD", "")

app = FastAPI(title="Analytics Service")

client = None


class AnalyticsEvent(BaseModel):
    event_type: str
    page: str = ""
    section: str = ""
    related_event_id: str = ""
    program_id: str = ""
    track: str = ""
    session_id: str = ""
    anonymous_user_id: str = ""
    metadata: Dict[str, Any] = Field(default_factory=dict)


def get_clickhouse_client():
    global client

    if client is None:
        client = clickhouse_connect.get_client(
            host=CLICKHOUSE_HOST,
            port=CLICKHOUSE_PORT,
            username=CLICKHOUSE_USER,
            password=CLICKHOUSE_PASSWORD,
            database=CLICKHOUSE_DATABASE,
        )

    return client


def create_table_if_not_exists():
    ch = get_clickhouse_client()

    ch.command("""
        CREATE TABLE IF NOT EXISTS analytics_events (
            analytics_event_id UUID,
            event_type String,
            page String,
            section String,
            related_event_id String,
            program_id String,
            track String,
            session_id String,
            anonymous_user_id String,
            metadata String,
            timestamp DateTime64(3, 'UTC')
        )
        ENGINE = MergeTree
        ORDER BY (timestamp, event_type)
    """)


@app.on_event("startup")
def startup_event():
    last_error = None

    for attempt in range(30):
        try:
            create_table_if_not_exists()
            print("ClickHouse table is ready")
            return
        except Exception as error:
            last_error = error
            print(f"Waiting for ClickHouse... attempt {attempt + 1}/30")
            time.sleep(2)

    raise last_error


@app.get("/")
def root():
    return {
        "service": "analytics-service",
        "status": "running"
    }


@app.get("/analytics/health")
def health_check():
    ch = get_clickhouse_client()
    result = ch.query("SELECT count() FROM analytics_events")

    return {
        "service": "analytics-service",
        "status": "running",
        "analytics_events_count": result.result_rows[0][0]
    }


@app.post("/analytics/events")
def save_analytics_event(event: AnalyticsEvent):
    ch = get_clickhouse_client()

    row = [
        str(uuid.uuid4()),
        event.event_type,
        event.page,
        event.section,
        event.related_event_id,
        event.program_id,
        event.track,
        event.session_id,
        event.anonymous_user_id,
        json.dumps(event.metadata),
        datetime.now(timezone.utc),
    ]

    ch.insert(
        "analytics_events",
        [row],
        column_names=[
            "analytics_event_id",
            "event_type",
            "page",
            "section",
            "related_event_id",
            "program_id",
            "track",
            "session_id",
            "anonymous_user_id",
            "metadata",
            "timestamp",
        ],
    )

    return {
        "message": "Analytics event saved",
        "event_type": event.event_type
    }


@app.get("/analytics/events")
def get_recent_events():
    ch = get_clickhouse_client()

    result = ch.query("""
        SELECT
            analytics_event_id,
            event_type,
            page,
            section,
            related_event_id,
            program_id,
            track,
            session_id,
            anonymous_user_id,
            metadata,
            timestamp
        FROM analytics_events
        ORDER BY timestamp DESC
        LIMIT 20
    """)

    events = []

    for row in result.result_rows:
        events.append({
            "analytics_event_id": str(row[0]),
            "event_type": row[1],
            "page": row[2],
            "section": row[3],
            "related_event_id": row[4],
            "program_id": row[5],
            "track": row[6],
            "session_id": row[7],
            "anonymous_user_id": row[8],
            "metadata": row[9],
            "timestamp": row[10],
        })

    return events
