from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, JSON, DateTime, ForeignKey, Boolean
from .database import Base


def now():
    return datetime.utcnow()


class Invoice(Base):
    __tablename__ = "invoices"
    id = Column(Integer, primary_key=True)
    org_id = Column(String, default="org_demo")
    filename = Column(String)
    file_path = Column(String)
    file_type = Column(String)
    status = Column(String, default="uploaded")  # uploaded / analyzed
    uploaded_at = Column(DateTime, default=now)


class PurchaseCategory(Base):
    __tablename__ = "purchase_categories"
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True)
    default_method = Column(String, default="spend")
    factor_kg_per_inr = Column(Float)  # emission factor lives here (mock data)
    factor_source = Column(String, default="Mock hackathon factor")


class InvoiceLineItem(Base):
    __tablename__ = "invoice_line_items"
    id = Column(Integer, primary_key=True)
    invoice_id = Column(Integer, ForeignKey("invoices.id"), nullable=True)
    supplier_name = Column(String)
    description = Column(String)
    quantity = Column(Float)
    unit = Column(String)
    unit_price = Column(Float)
    total_amount = Column(Float)
    currency = Column(String, default="INR")
    date = Column(String)
    category_id = Column(Integer, ForeignKey("purchase_categories.id"))
    classification_confidence = Column(Float, default=1.0)


class EmissionEstimate(Base):
    __tablename__ = "emission_estimates"
    id = Column(Integer, primary_key=True)
    line_item_id = Column(Integer, ForeignKey("invoice_line_items.id"))
    co2e_kg = Column(Float)
    method = Column(String)  # spend / activity
    confidence = Column(String)  # low / medium / high
    data_flags = Column(JSON, default=list)


class SupplierAlternative(Base):
    """One row per supplier option per category. is_current marks the baseline supplier."""
    __tablename__ = "supplier_alternatives"
    id = Column(Integer, primary_key=True)
    category_id = Column(Integer, ForeignKey("purchase_categories.id"))
    supplier_name = Column(String)
    location = Column(String)
    certifications = Column(JSON, default=list)
    recycled_content_pct = Column(Float, default=0)
    verified = Column(Boolean, default=False)
    is_current = Column(Boolean, default=False)
    price_delta_pct = Column(Float, default=0)   # vs current supplier
    lead_time_days = Column(Integer)
    co2e_ratio = Column(Float, default=1.0)      # emissions relative to current supplier (1.0 = same)
    confidence = Column(String, default="medium")
    source = Column(String, default="Supplier-declared (unverified)")


class Recommendation(Base):
    __tablename__ = "recommendations"
    id = Column(Integer, primary_key=True)
    category_id = Column(Integer, ForeignKey("purchase_categories.id"))
    title = Column(String)
    summary = Column(String)
    base_co2e_kg = Column(Float)
    base_spend = Column(Float)
    options = Column(JSON, default=list)
    assumptions = Column(JSON, default=list)
    evidence = Column(JSON, default=list)
    missing_data = Column(JSON, default=list)
    draft_email = Column(String)
    approval_status = Column(String, default="pending")  # pending / approved / rejected
    decision_comment = Column(String)
    decided_by = Column(String)
    decided_at = Column(DateTime)
    created_at = Column(DateTime, default=now)


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id = Column(Integer, primary_key=True)
    org_id = Column(String, default="org_demo")
    event_type = Column(String)
    detail = Column(JSON, default=dict)
    timestamp = Column(DateTime, default=now)
