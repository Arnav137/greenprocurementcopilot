from ..models import AuditLog


def log_event(db, event_type: str, detail: dict | None = None):
    db.add(AuditLog(event_type=event_type, detail=detail or {}))
    db.commit()
