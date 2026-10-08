from __future__ import annotations

import asyncio
import sqlite3
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

DB_PATH = Path(__file__).with_name("turnos.db")
db_lock = asyncio.Lock()
clients: set[WebSocket] = set()


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def initialize() -> None:
    with connect() as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS tickets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL CHECK(status IN ('waiting','in_service','done')),
            table_id INTEGER,
            created_at TEXT NOT NULL,
            started_at TEXT,
            finished_at TEXT
        );
        CREATE TABLE IF NOT EXISTS service_tables (
            id INTEGER PRIMARY KEY,
            ticket_id INTEGER REFERENCES tickets(id)
        );
        """)
        for table_id in range(1, 5):
            db.execute("INSERT OR IGNORE INTO service_tables(id) VALUES (?)", (table_id,))


def read_state(db: sqlite3.Connection) -> dict[str, Any]:
    tables = []
    for row in db.execute("SELECT id,ticket_id FROM service_tables ORDER BY id"):
        ticket = db.execute("SELECT id,name,created_at,started_at FROM tickets WHERE id=?", (row["ticket_id"],)).fetchone() if row["ticket_id"] else None
        tables.append({"id": row["id"], "ticket": dict(ticket) if ticket else None})
    queue = [dict(row) for row in db.execute("SELECT id,name,created_at FROM tickets WHERE status='waiting' ORDER BY id")]
    active = [t for t in tables if t["ticket"]]
    current = min(active, key=lambda t: t["ticket"].get("started_at") or "") if active else None
    return {"tables": tables, "queue": queue, "current": current, "next_number": (db.execute("SELECT COALESCE(MAX(id),0)+1 FROM tickets").fetchone()[0])}


async def snapshot() -> dict[str, Any]:
    with connect() as db:
        return read_state(db)


async def publish() -> None:
    state = await snapshot()
    gone = []
    for ws in list(clients):
        try:
            await ws.send_json(state)
        except Exception:
            gone.append(ws)
    for ws in gone:
        clients.discard(ws)


@asynccontextmanager
async def lifespan(_: FastAPI):
    initialize()
    yield


app = FastAPI(title="Sistema de Turnos", version="1.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:4200", "http://127.0.0.1:4200"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])


class NewTicket(BaseModel):
    name: str = Field(default="", max_length=60)


@app.get("/api/state")
async def get_state():
    return await snapshot()


@app.post("/api/tickets", status_code=201)
async def create_ticket(payload: NewTicket):
    async with db_lock:
        with connect() as db:
            db.execute("BEGIN IMMEDIATE")
            now = datetime.now().astimezone().isoformat(timespec="seconds")
            cursor = db.execute("INSERT INTO tickets(name,status,created_at) VALUES (?, 'waiting', ?)", (payload.name.strip(), now))
            ticket_id = cursor.lastrowid
            free = db.execute("SELECT id FROM service_tables WHERE ticket_id IS NULL ORDER BY id LIMIT 1").fetchone()
            if free:
                db.execute("UPDATE tickets SET status='in_service',table_id=?,started_at=? WHERE id=?", (free["id"], now, ticket_id))
                db.execute("UPDATE service_tables SET ticket_id=? WHERE id=?", (ticket_id, free["id"]))
            db.commit()
            result = {"id": ticket_id, "name": payload.name.strip(), "status": "in_service" if free else "waiting", "table_id": free["id"] if free else None}
    await publish()
    return result


@app.post("/api/tables/{table_id}/finish")
async def finish_service(table_id: int):
    if not 1 <= table_id <= 4:
        raise HTTPException(status_code=404, detail="Mesa no encontrada")
    async with db_lock:
        with connect() as db:
            db.execute("BEGIN IMMEDIATE")
            table = db.execute("SELECT ticket_id FROM service_tables WHERE id=?", (table_id,)).fetchone()
            if not table or table["ticket_id"] is None:
                raise HTTPException(status_code=409, detail="La mesa ya está disponible")
            db.execute("UPDATE tickets SET status='done',finished_at=? WHERE id=?", (datetime.now().astimezone().isoformat(timespec="seconds"), table["ticket_id"]))
            next_ticket = db.execute("SELECT id FROM tickets WHERE status='waiting' ORDER BY id LIMIT 1").fetchone()
            if next_ticket:
                now = datetime.now().astimezone().isoformat(timespec="seconds")
                db.execute("UPDATE tickets SET status='in_service',table_id=?,started_at=? WHERE id=?", (table_id, now, next_ticket["id"]))
                db.execute("UPDATE service_tables SET ticket_id=? WHERE id=?", (next_ticket["id"], table_id))
            else:
                db.execute("UPDATE service_tables SET ticket_id=NULL WHERE id=?", (table_id,))
            db.commit()
    await publish()
    return await snapshot()


@app.post("/api/reset")
async def reset_day():
    async with db_lock:
        with connect() as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute("DELETE FROM service_tables")
            db.execute("DELETE FROM tickets")
            db.execute("DELETE FROM sqlite_sequence WHERE name='tickets'")
            for table_id in range(1, 5):
                db.execute("INSERT INTO service_tables(id) VALUES (?)", (table_id,))
            db.commit()
    await publish()
    return await snapshot()


@app.websocket("/ws")
async def websocket_state(ws: WebSocket):
    await ws.accept()
    clients.add(ws)
    await ws.send_json(await snapshot())
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        clients.discard(ws)
