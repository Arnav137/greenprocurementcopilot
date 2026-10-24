from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Recommendation, SupplierAlternative, AuditLog
from ..services.audit import log_event
from ..services.scenario import compute_scenario
from ..integrations.pdf_report import generate_pdf

router = APIRouter(tags=["recommendations"])


class ScenarioIn(BaseModel):
    alternative_id: int
    volume_share: float = 0.6


class DecisionIn(BaseModel):
    comment: str | None = None
    actor: str = "demo_user"


def rec_to_dict(r: Recommendation) -> dict:
    return {"id": r.id, "category_id": r.category_id, "title": r.title, "summary": r.summary,
            "base_co2e_kg": r.base_co2e_kg, "base_spend": r.base_spend, "options": r.options,
            "assumptions": r.assumptions, "evidence": r.evidence, "missing_data": r.missing_data,
            "draft_email": r.draft_email, "approval_status": r.approval_status,
            "decision_comment": r.decision_comment, "decided_by": r.decided_by, "decided_at": r.decided_at}


def _get(db, rec_id) -> Recommendation:
    rec = db.get(Recommendation, rec_id)
    if not rec:
        raise HTTPException(404, "Recommendation not found")
    return rec


@router.get("/recommendations")
def list_recs(db: Session = Depends(get_db)):
    return [rec_to_dict(r) for r in db.query(Recommendation).order_by(Recommendation.base_co2e_kg.desc()).all()]


@router.get("/recommendations/{rec_id}")
def get_rec(rec_id: int, db: Session = Depends(get_db)):
    return rec_to_dict(_get(db, rec_id))


@router.post("/recommendations/{rec_id}/scenario")
def scenario(rec_id: int, body: ScenarioIn, db: Session = Depends(get_db)):
    rec = _get(db, rec_id)
    alt = db.get(SupplierAlternative, body.alternative_id)
    if not alt or alt.category_id != rec.category_id:
        raise HTTPException(400, "alternative_id does not belong to this recommendation's category")
    res = compute_scenario(rec.base_co2e_kg, rec.base_spend, alt.co2e_ratio, alt.price_delta_pct, body.volume_share)
    res.update(supplier=alt.supplier_name, lead_time_days=alt.lead_time_days)
    log_event(db, "scenario_run", {"recommendation_id": rec_id, "alternative_id": alt.id, "share": body.volume_share})
    return res


def _decide(db, rec_id, status, body: DecisionIn):
    rec = _get(db, rec_id)
    rec.approval_status, rec.decision_comment = status, body.comment
    rec.decided_by, rec.decided_at = body.actor, datetime.utcnow()
    db.commit()
    log_event(db, f"recommendation_{status}", {"recommendation_id": rec_id, "actor": body.actor, "comment": body.comment})
    return rec_to_dict(rec)


@router.post("/recommendations/{rec_id}/approve")
def approve(rec_id: int, body: DecisionIn = DecisionIn(), db: Session = Depends(get_db)):
    return _decide(db, rec_id, "approved", body)


@router.post("/recommendations/{rec_id}/reject")
def reject(rec_id: int, body: DecisionIn = DecisionIn(), db: Session = Depends(get_db)):
    return _decide(db, rec_id, "rejected", body)


@router.get("/recommendations/{rec_id}/report")
def report(rec_id: int, db: Session = Depends(get_db)):
    rec = _get(db, rec_id)
    if rec.approval_status != "approved":  # the human-in-the-loop gate
        raise HTTPException(403, "Report is only available after human approval")
    path = generate_pdf(rec_to_dict(rec))
    log_event(db, "report_generated", {"recommendation_id": rec_id})
    return FileResponse(path, media_type="application/pdf", filename=f"recommendation_{rec_id}.pdf")


@router.get("/audit-logs")
def audit_logs(limit: int = 100, db: Session = Depends(get_db)):
    rows = db.query(AuditLog).order_by(AuditLog.id.desc()).limit(limit).all()
    return [{"id": a.id, "event_type": a.event_type, "detail": a.detail, "timestamp": a.timestamp} for a in rows]
