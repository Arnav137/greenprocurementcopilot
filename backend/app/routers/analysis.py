from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import PurchaseCategory, InvoiceLineItem, EmissionEstimate, SupplierAlternative
from ..services import pipeline
from ..services.audit import log_event
from ..integrations.ai_workflow import demo_items, _classify

router = APIRouter(tags=["analysis"])


@router.post("/analysis/run")
def run(bg: BackgroundTasks, db: Session = Depends(get_db)):
    run_id = pipeline.new_run()
    log_event(db, "analysis_started", {"run_id": run_id})
    bg.add_task(pipeline.execute_pipeline, run_id)
    return {"run_id": run_id}


@router.get("/analysis/{run_id}")
def status(run_id: str):
    if run_id not in pipeline.RUNS:
        raise HTTPException(404, "Unknown run_id")
    return pipeline.RUNS[run_id]


@router.get("/hotspots")
def hotspots(limit: int = 5, db: Session = Depends(get_db)):
    by_cat = (db.query(PurchaseCategory.id, PurchaseCategory.name, func.sum(EmissionEstimate.co2e_kg),
                       func.sum(InvoiceLineItem.total_amount))
              .join(InvoiceLineItem, InvoiceLineItem.category_id == PurchaseCategory.id)
              .join(EmissionEstimate, EmissionEstimate.line_item_id == InvoiceLineItem.id)
              .group_by(PurchaseCategory.id).order_by(func.sum(EmissionEstimate.co2e_kg).desc()).limit(limit).all())
    by_sup = (db.query(InvoiceLineItem.supplier_name, func.sum(EmissionEstimate.co2e_kg))
              .join(EmissionEstimate, EmissionEstimate.line_item_id == InvoiceLineItem.id)
              .group_by(InvoiceLineItem.supplier_name).order_by(func.sum(EmissionEstimate.co2e_kg).desc())
              .limit(limit).all())
    total = sum(r[2] or 0 for r in by_cat) or 1
    return {"by_category": [{"category_id": i, "category": n, "co2e_kg": round(c or 0, 1), "spend_inr": s,
                             "share_pct": round((c or 0) / total * 100, 1)} for i, n, c, s in by_cat],
            "by_supplier": [{"supplier": n, "co2e_kg": round(c or 0, 1)} for n, c in by_sup]}


@router.post("/demo/load")
def load_demo(db: Session = Depends(get_db)):
    """FALLBACK: loads pre-baked demo data without invoices or AI. Use if live extraction fails."""
    items = demo_items()
    for it in items:
        it["category"], it["confidence"] = _classify(it["description"])
    pipeline.persist_state(db, {"classified_items": items})
    log_event(db, "demo_data_loaded", {"items": len(items)})
    return {"loaded_items": len(items)}
