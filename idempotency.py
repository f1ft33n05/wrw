import json
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, Request

from database_models import IdempotencyKey


def get_cached_response(db, request: Request):
    key = request.headers.get("Idempotency-Key")
    if not key:
        return None
    record = db.query(IdempotencyKey).filter(IdempotencyKey.key == key).first()
    if record is None:
        return None
    if record.method != request.method or record.path != request.url.path:
        raise HTTPException(status_code=422, detail="Idempotency key was used with a different operation")
    return record.response_status, json.loads(record.response_body)


def save_response(db, request: Request, status_code: int, body) -> None:
    key = request.headers.get("Idempotency-Key")
    if not key:
        return
    record = IdempotencyKey(
        key=key,
        method=request.method,
        path=request.url.path,
        response_status=status_code,
        response_body=json.dumps(body, default=str),
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    db.add(record)


def require_idempotency_key(request: Request) -> str:
    key = request.headers.get("Idempotency-Key", "").strip()
    if not key:
        raise HTTPException(status_code=400, detail="Idempotency-Key header is required")
    if len(key) > 128:
        raise HTTPException(status_code=422, detail="Idempotency-Key is too long")
    return key
