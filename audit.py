from datetime import datetime, timezone

from database_models import AuditEvent


def record_audit_event(
    db,
    *,
    action: str,
    outcome: str,
    actor=None,
    resource_type: str | None = None,
    resource_id: str | None = None,
    ip_address: str | None = None,
) -> None:
    db.add(AuditEvent(
        occurred_at=datetime.now(timezone.utc).isoformat(),
        actor_id=actor.get("id") if actor else None,
        actor_name=actor.get("username") if actor else None,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        ip_address=ip_address,
        outcome=outcome,
    ))
