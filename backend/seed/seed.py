"""Run: python -m seed.seed   (re-runnable; wipes categories + alternatives and reloads)"""
from app.database import SessionLocal, Base, engine
from app import models as m

Base.metadata.create_all(engine)

# factor_kg_per_inr are MOCK numbers for the demo. Corrugated: 1840 kg / Rs 1,20,000 (from the project doc).
CATEGORIES = [
    ("Corrugated Packaging", 0.01533), ("Plastic Packaging", 0.0250), ("Freight & Logistics", 0.0180),
    ("Metal & Steel", 0.0300), ("Office Supplies", 0.0050), ("Other", 0.0100),
]
# (category, supplier, location, certs, recycled%, verified, is_current, price_delta%, lead_days, co2e_ratio, confidence)
ALTERNATIVES = [
    ("Corrugated Packaging", "Supplier A", "Chennai", [], 10, True, True, 0, 4, 1.0, "medium"),
    ("Corrugated Packaging", "Supplier B", "Hyderabad", ["FSC (claimed)"], 70, False, False, 6, 6, 1150 / 1840, "high"),
    ("Corrugated Packaging", "Supplier C", "Bengaluru (local)", [], 25, False, False, 12, 2, 1320 / 1840, "medium"),
    ("Plastic Packaging", "PackWrap Ltd", "Pune", [], 0, True, True, 0, 5, 1.0, "medium"),
    ("Plastic Packaging", "EcoFilm Pvt Ltd", "Mumbai", ["Recycled content (claimed)"], 60, False, False, 9, 7, 0.55, "medium"),
    ("Plastic Packaging", "GreenWrap Co", "Bengaluru (local)", [], 30, False, False, 4, 3, 0.80, "low"),
    ("Freight & Logistics", "FastMove Logistics", "Bengaluru", [], 0, True, True, 0, 2, 1.0, "medium"),
    ("Freight & Logistics", "RailLink Cargo", "Bengaluru", ["Rail-based (claimed)"], 0, False, False, -5, 4, 0.45, "medium"),
]

db = SessionLocal()
for model in (m.Recommendation, m.EmissionEstimate, m.InvoiceLineItem, m.SupplierAlternative, m.PurchaseCategory):
    db.query(model).delete()
db.commit()

ids = {}
for name, factor in CATEGORIES:
    c = m.PurchaseCategory(name=name, factor_kg_per_inr=factor)
    db.add(c); db.flush(); ids[name] = c.id
for cat, sup, loc, certs, rec, ver, cur, price, lead, ratio, conf in ALTERNATIVES:
    db.add(m.SupplierAlternative(category_id=ids[cat], supplier_name=sup, location=loc, certifications=certs,
                                 recycled_content_pct=rec, verified=ver, is_current=cur, price_delta_pct=price,
                                 lead_time_days=lead, co2e_ratio=ratio, confidence=conf))
db.commit()
print(f"Seeded {len(CATEGORIES)} categories and {len(ALTERNATIVES)} supplier options.")
