import json
import queue
import threading
import zlib
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import (Column, DateTime, Integer, LargeBinary, String, Text,
                        UniqueConstraint, create_engine)
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import declarative_base, sessionmaker

import config
import matlab_bridge

# ------------------------------------------------------------------ database
connect_args = {"check_same_thread": False} if config.DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(config.DATABASE_URL, connect_args=connect_args, pool_pre_ping=True)
Session = sessionmaker(bind=engine, expire_on_commit=False)
Base = declarative_base()


def now():
    return datetime.now(timezone.utc)


class Case(Base):
    """One row per distinct set of inputs. The result is zlib-compressed JSON, so big curves stay small."""
    __tablename__ = "consolidation_cases_hours"
    __table_args__ = (UniqueConstraint("params_key", name="uq_params_hours"),)
    id = Column(Integer, primary_key=True)
    params_key = Column(String(300), nullable=False)  # canonical JSON of the inputs
    status = Column(String(10), nullable=False, default="pending")  # pending|running|done|failed
    error = Column(Text)
    result = Column(LargeBinary)
    created_at = Column(DateTime(timezone=True), default=now)
    updated_at = Column(DateTime(timezone=True), default=now)


def load_result(case):
    return json.loads(zlib.decompress(case.result)) if case.result else None


def public(case, cached=None):
    body = {"id": case.id, "params": json.loads(case.params_key),
            "status": case.status, "error": case.error}
    if cached is not None:
        body["cached"] = cached
    if case.status == "done":
        body["data"] = load_result(case)
    return body


# ------------------------------------------------------------------ worker
# ONE worker thread: MATLAB runs one case at a time (one licence, and the engine is single-threaded).
# Requests for the same new case never start a second run: they share the same row.
jobs: "queue.Queue[int]" = queue.Queue()


def worker():
    matlab_bridge.init()
    while True:
        case_id = jobs.get()
        with Session() as s:
            case = s.get(Case, case_id)
            if case is None or case.status == "done":
                continue
            case.status, case.error = "running", None
            s.commit()
            try:
                result = matlab_bridge.compute(json.loads(case.params_key))
                case.result = zlib.compress(json.dumps(result).encode())
                case.status = "done"
            except Exception as exc:  # noqa: BLE001
                case.status, case.error = "failed", str(exc)[:2000]
            case.updated_at = now()
            s.commit()


@asynccontextmanager
async def lifespan(_app):
    Base.metadata.create_all(engine)
    with Session() as s:  # anything left unfinished by a restart goes back in the queue
        for case in s.query(Case).filter(Case.status.in_(["pending", "running"])).order_by(Case.id):
            case.status = "pending"
            jobs.put(case.id)
        s.commit()
    threading.Thread(target=worker, daemon=True).start()
    yield


app = FastAPI(title="Soil settlement", lifespan=lifespan)


# ------------------------------------------------------------------ API
class CaseRequest(BaseModel):
    ks: float
    mv: float
    thickness: float
    u0: float
    drainage: str


@app.get("/api/options")
def options():
    return {"params": config.PARAMS, "drainage_types": config.DRAINAGE_TYPES,
            "mode": config.MATLAB_MODE}


@app.post("/api/cases")
def request_case(req: CaseRequest):
    try:
        clean = matlab_bridge.validate(req.model_dump())
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    key = json.dumps(clean, sort_keys=True)
    with Session() as s:
        def find():
            return s.query(Case).filter_by(params_key=key).first()

        case = find()
        if case and case.status == "done":
            return public(case, cached=True)  # 1) in the database -> just return it
        if case is None:  # 2) not there -> create the row, queue a MATLAB run
            case = Case(params_key=key)
            s.add(case)
            try:
                s.commit()
                jobs.put(case.id)
            except IntegrityError:  # someone else created it a moment ago
                s.rollback()
                case = find()
        elif case.status == "failed":  # retry a failed case
            case.status, case.error = "pending", None
            s.commit()
            jobs.put(case.id)
        return public(case, cached=False)


@app.get("/api/cases/{case_id}")
def get_case(case_id: int):
    with Session() as s:
        case = s.get(Case, case_id)
        if case is None:
            raise HTTPException(404, "No such case")
        return public(case)


@app.get("/")
def index():
    return FileResponse(Path(__file__).parent.parent / "frontend" / "index.html")
