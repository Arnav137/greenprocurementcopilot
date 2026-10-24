from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import SupplierAlternative, PurchaseCategory

router = APIRouter(tags=["suppliers"])


@router.get("/categories")
def categories(db: Session = Depends(get_db)):
    return [{"id": c.id, "name": c.name, "factor_kg_per_inr": c.factor_kg_per_inr, "factor_source": c.factor_source}
            for c in db.query(PurchaseCategory).all()]


@router.get("/suppliers/alternatives")
def alternatives(category_id: int | None = None, db: Session = Depends(get_db)):
    q = db.query(SupplierAlternative)
    if category_id:
        q = q.filter_by(category_id=category_id)
    return [{"id": a.id, "category_id": a.category_id, "supplier": a.supplier_name, "location": a.location,
             "is_current": a.is_current, "certifications": a.certifications,
             "recycled_content_pct": a.recycled_content_pct, "verified": a.verified,
             "price_delta_pct": a.price_delta_pct, "lead_time_days": a.lead_time_days,
             "co2e_ratio": a.co2e_ratio, "confidence": a.confidence, "source": a.source} for a in q.all()]
