import uuid
from datetime import datetime
from sqlalchemy import func

from ..database import SessionLocal
from ..models import (Invoice, InvoiceLineItem, PurchaseCategory, EmissionEstimate,
                      SupplierAlternative, Recommendation)
from ..integrations.ai_workflow import run_workflow
from ..integrations.emissions import calculate_co2e
from .file_service import extract_text
from .scenario import compute_scenario
from .audit import log_event

RUNS: dict = {}  # in-memory run status (no table needed)


def new_run() -> str:
    run_id = uuid.uuid4().hex[:8]
    RUNS[run_id] = {"run_id": run_id, "status": "queued", "current_step": "queued", "error": None}
    return run_id


def _set(run_id, status, step=None, error=None):
    RUNS[run_id].update(status=status, error=error)
    if step:
        RUNS[run_id]["current_step"] = step


def build_initial_state(db) -> dict:
    docs = []
    for inv in db.query(Invoice).all():
        try:
            docs.append({"invoice_id": inv.id, "filename": inv.filename,
                         "text": extract_text(inv.file_path, inv.file_type)})
        except Exception as e:
            log_event(db, "extraction_failed", {"invoice_id": inv.id, "error": str(e)})
    return {"organization_id": "org_demo", "raw_documents": docs, "extracted_items": [],
            "classified_items": [], "emission_estimates": [], "hotspots": [], "supplier_options": [],
            "recommendation": {}, "missing_data_requests": [], "approval_status": "pending", "audit_trail": []}


def persist_state(db, state: dict):
    """Turn the workflow state dict into DB rows. Idempotent: wipes previous results first."""
    db.query(Recommendation).delete()
    db.query(EmissionEstimate).delete()
    db.query(InvoiceLineItem).delete()
    db.commit()

    cats = {c.name.lower(): c for c in db.query(PurchaseCategory).all()}
    other = cats.get("other")
    for it in state.get("classified_items", []):
        cat = cats.get(str(it.get("category", "")).lower(), other)
        conf = float(it.get("confidence", 1.0))
        li = InvoiceLineItem(invoice_id=it.get("invoice_id"), supplier_name=it.get("supplier_name"),
                             description=it.get("description"), quantity=it.get("quantity"), unit=it.get("unit"),
                             unit_price=it.get("unit_price"), total_amount=it.get("total_amount"),
                             date=it.get("date"), category_id=cat.id, classification_confidence=conf)
        db.add(li)
        db.flush()
        est = calculate_co2e(cat.factor_kg_per_inr, li.total_amount, conf)
        db.add(EmissionEstimate(line_item_id=li.id, **est))
    db.commit()

    # one recommendation per hotspot category that has supplier alternatives
    ai_recs = state.get("recommendation") or []
    if isinstance(ai_recs, dict):
        ai_recs = [ai_recs] if ai_recs else []
    ai_by_cat = {str(r.get("category", "")).lower(): r for r in ai_recs}

    rows = (db.query(PurchaseCategory, func.sum(EmissionEstimate.co2e_kg), func.sum(InvoiceLineItem.total_amount))
            .join(InvoiceLineItem, InvoiceLineItem.category_id == PurchaseCategory.id)
            .join(EmissionEstimate, EmissionEstimate.line_item_id == InvoiceLineItem.id)
            .group_by(PurchaseCategory.id).order_by(func.sum(EmissionEstimate.co2e_kg).desc()).all())
    for cat, base_co2e, base_spend in rows:
        alts = db.query(SupplierAlternative).filter_by(category_id=cat.id).all()
        if len(alts) < 2:
            continue
        options = [{"alternative_id": a.id, "supplier": a.supplier_name, "is_current": a.is_current,
                    "cost_impact_pct": a.price_delta_pct, "co2e_kg": round(base_co2e * a.co2e_ratio, 1),
                    "lead_time_days": a.lead_time_days, "confidence": a.confidence,
                    "recycled_content_pct": a.recycled_content_pct, "verified": a.verified,
                    "certifications": a.certifications, "source": a.source} for a in alts]
        current = next((a for a in alts if a.is_current), alts[0])
        best = min((a for a in alts if a is not current), key=lambda a: a.co2e_ratio)
        sc = compute_scenario(base_co2e, base_spend, best.co2e_ratio, best.price_delta_pct, 0.6)
        ai = ai_by_cat.get(cat.name.lower(), {})
        summary = ai.get("summary") or (
            f"Shift 60% of {cat.name} volume from {current.supplier_name} to {best.supplier_name}: "
            f"about {sc['reduction_pct']}% lower CO2e for about {sc['cost_delta_pct']}% higher cost "
            f"(a full switch gives {round((1 - best.co2e_ratio) * 100, 1)}% lower CO2e). "
            f"Based on spend-based factors; refine with supplier-specific data.")
        db.add(Recommendation(
            category_id=cat.id, base_co2e_kg=round(base_co2e, 1), base_spend=base_spend, options=options,
            title=ai.get("title") or f"Switch part of {cat.name} to {best.supplier_name}", summary=summary,
            assumptions=ai.get("assumptions") or [f"Spend-based emission factor ({cat.factor_source})",
                                                  "Alternative emissions scaled from supplier-declared data",
                                                  "Prices and lead times from the mock supplier dataset"],
            evidence=ai.get("evidence") or [f"{best.supplier_name}: {best.recycled_content_pct:.0f}% recycled content "
                                            f"({'verified' if best.verified else 'unverified supplier claim'})"],
            missing_data=ai.get("missing_data") or ["Material weight / activity data per unit",
                                                    "Verified sustainability certificates",
                                                    "Written quotation from alternative suppliers"],
            draft_email=ai.get("draft_email") or (
                f"Subject: Request for quotation and sustainability data - {cat.name}\n\n"
                f"Hello {best.supplier_name} team,\n\nWe are reviewing our {cat.name} sourcing. Could you share a quote, "
                f"lead times, and supporting documents for your sustainability claims (material composition, "
                f"certifications)?\n\nThank you.\n\n[DRAFT - not sent. Requires human approval.]")))
    db.commit()


def execute_pipeline(run_id: str):
    db = SessionLocal()
    try:
        _set(run_id, "running", "extracting")
        state = build_initial_state(db)
        if not state["raw_documents"]:
            raise ValueError("No invoices uploaded yet")
        _set(run_id, "running", "analyzing")
        state = run_workflow(state)
        _set(run_id, "running", "saving")
        persist_state(db, state)
        db.query(Invoice).update({"status": "analyzed"})
        db.commit()
        log_event(db, "analysis_completed", {"run_id": run_id, "items": len(state.get("classified_items", []))})
        _set(run_id, "done", "done")
    except Exception as e:
        db.rollback()
        log_event(db, "analysis_failed", {"run_id": run_id, "error": str(e)})
        _set(run_id, "failed", "failed", str(e))
    finally:
        db.close()
