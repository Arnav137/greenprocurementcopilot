import os
from uuid import uuid4
from fastapi import APIRouter, Depends, UploadFile, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Invoice, InvoiceLineItem, PurchaseCategory
from ..services.audit import log_event
from ..config import UPLOAD_DIR, ALLOWED_TYPES

router = APIRouter(tags=["invoices"])


@router.post("/invoices/upload")
async def upload(files: list[UploadFile], db: Session = Depends(get_db)):
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    out = []
    for f in files:
        ext = f.filename.rsplit(".", 1)[-1].lower() if "." in f.filename else ""
        if ext not in ALLOWED_TYPES:
            raise HTTPException(400, f"Unsupported file type '.{ext}'. Allowed: {sorted(ALLOWED_TYPES)}")
        path = os.path.join(UPLOAD_DIR, f"{uuid4().hex}_{f.filename}")
        with open(path, "wb") as buf:
            buf.write(await f.read())
        inv = Invoice(filename=f.filename, file_path=path, file_type=ext)
        db.add(inv)
        db.commit()
        db.refresh(inv)
        log_event(db, "invoice_uploaded", {"invoice_id": inv.id, "filename": f.filename})
        out.append({"id": inv.id, "filename": inv.filename, "status": inv.status})
    return out


@router.get("/invoices")
def list_invoices(db: Session = Depends(get_db)):
    return [{"id": i.id, "filename": i.filename, "file_type": i.file_type, "status": i.status,
             "uploaded_at": i.uploaded_at} for i in db.query(Invoice).order_by(Invoice.id).all()]


@router.get("/line-items")
def line_items(db: Session = Depends(get_db)):
    from ..models import EmissionEstimate
    rows = (db.query(InvoiceLineItem, PurchaseCategory, EmissionEstimate)
            .join(PurchaseCategory, PurchaseCategory.id == InvoiceLineItem.category_id)
            .outerjoin(EmissionEstimate, EmissionEstimate.line_item_id == InvoiceLineItem.id).all())
    return [{"id": li.id, "invoice_id": li.invoice_id, "supplier_name": li.supplier_name,
             "description": li.description, "quantity": li.quantity, "unit": li.unit,
             "unit_price": li.unit_price, "total_amount": li.total_amount, "currency": li.currency,
             "date": li.date, "category_id": c.id, "category": c.name,
             "classification_confidence": li.classification_confidence,
             "co2e_kg": e.co2e_kg if e else None, "method": e.method if e else None,
             "confidence": e.confidence if e else None, "data_flags": e.data_flags if e else []}
            for li, c, e in rows]
