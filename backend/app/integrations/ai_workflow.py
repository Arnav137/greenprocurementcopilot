"""
STUB for the AI dev to replace. Keep the signature: run_workflow(state: dict) -> dict

INPUT state:
  raw_documents: [{"invoice_id": int, "filename": str, "text": str}]

MUST RETURN (same dict, with these keys filled):
  classified_items: [{
      "invoice_id": int | None, "supplier_name": str, "description": str,
      "quantity": float, "unit": str, "unit_price": float, "total_amount": float,
      "date": str, "category": str,          # must match a category name in the DB (see seed)
      "confidence": float                    # 0-1 classification confidence
  }]
OPTIONAL (backend fills sensible defaults if missing):
  recommendation: {"category": str, "title": str, "summary": str, "assumptions": [str],
                   "evidence": [str], "missing_data": [str], "draft_email": str}
  (or a list of those dicts, one per category)
  missing_data_requests: [str]

Categories: Corrugated Packaging, Plastic Packaging, Freight & Logistics, Metal & Steel, Office Supplies, Other
"""
import csv
import io

KEYWORDS = {
    "Corrugated Packaging": ["corrugated", "carton", "cardboard", "box"],
    "Plastic Packaging": ["plastic", "poly", "stretch", "bubble", "wrap"],
    "Freight & Logistics": ["freight", "transport", "shipping", "courier", "logistics"],
    "Metal & Steel": ["steel", "metal", "aluminium", "aluminum", "iron"],
    "Office Supplies": ["paper", "pen", "stationery", "toner"],
}


def _classify(desc: str):
    d = desc.lower()
    for cat, words in KEYWORDS.items():
        if any(w in d for w in words):
            return cat, 0.9
    return "Other", 0.5


def demo_items():
    return [
        {"invoice_id": None, "supplier_name": "Supplier A", "description": "Corrugated boxes", "quantity": 5000,
         "unit": "pcs", "unit_price": 24, "total_amount": 120000, "date": "2026-10-01"},
        {"invoice_id": None, "supplier_name": "PackWrap Ltd", "description": "Plastic stretch wrap rolls",
         "quantity": 400, "unit": "rolls", "unit_price": 350, "total_amount": 140000, "date": "2026-10-03"},
        {"invoice_id": None, "supplier_name": "FastMove Logistics", "description": "Road freight - Bengaluru to Chennai",
         "quantity": 12, "unit": "trips", "unit_price": 9000, "total_amount": 108000, "date": "2026-10-05"},
    ]


def run_workflow(state: dict) -> dict:
    items = []
    for doc in state.get("raw_documents", []):
        try:  # works for CSV text with a header row containing 'description'
            rows = list(csv.DictReader(io.StringIO(doc["text"])))
            if rows and "description" in {k.lower() for k in rows[0]}:
                for r in rows:
                    r = {k.strip().lower(): v for k, v in r.items()}
                    items.append({"invoice_id": doc["invoice_id"], "supplier_name": r.get("supplier_name") or r.get("supplier", ""),
                                  "description": r["description"], "quantity": float(r.get("quantity") or 0),
                                  "unit": r.get("unit", ""), "unit_price": float(r.get("unit_price") or 0),
                                  "total_amount": float(r.get("total_amount") or 0), "date": r.get("date", "")})
        except Exception:
            pass
    if not items:  # PDFs (or unparseable files): fall back to demo items until the real agent exists
        items = demo_items()
        for i in items:
            i["invoice_id"] = (state["raw_documents"][0]["invoice_id"] if state.get("raw_documents") else None)
    for it in items:
        it["category"], it["confidence"] = _classify(it["description"])
    state["classified_items"] = items
    state["extracted_items"] = items
    return state
