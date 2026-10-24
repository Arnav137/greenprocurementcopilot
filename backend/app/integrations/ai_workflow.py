"""
AI workflow: structures raw invoice text into line items using Ollama, then classifies them.

Contract (unchanged):  run_workflow(state: dict) -> dict
  IN : state["raw_documents"] = [{"invoice_id", "filename", "text"}]
  OUT: state["classified_items"] = [{invoice_id, supplier_name, description, quantity, unit,
                                     unit_price, total_amount, date, category, confidence}]

Flow per document:
  CSV-style text with a 'description' column -> parsed directly (fast, no LLM needed)
  anything else (PDF text)                   -> Ollama extracts line items as JSON
  Ollama down / bad output                   -> demo items + a note in missing_data_requests
Category comes from keyword rules in code (reliable), not from the small LLM.

Call_ollama and parse_object are adapted from the AI dev's structure.py.
"""
import csv
import io
import json
import os
import re

import requests

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434/api/generate")
MODEL = os.getenv("OLLAMA_MODEL", "qwen3:1.7b")
MAX_CHARS = 6000  # truncate very long documents so the small model's context isn't overrun

PROMPT = """
Extract the purchased line items from the invoice text below.
Return exactly one JSON object in this shape:
{"items": [
  {"supplier_name": string or null, "description": string, "quantity": number or null,
   "unit": string or null, "unit_price": number or null, "total_amount": number or null,
   "date": string or null}
]}
Rules:
- One entry per purchased product or service line.
- Numbers must be plain numbers: no currency symbols, no commas (write 120000, not Rs 1,20,000).
- Use the supplier name that appears on the invoice for every item.
- Never invent values. Use null when something is not stated.
- Return JSON only; no markdown and no explanation.
"""

KEYWORDS = {
    "Corrugated Packaging": ["corrugated", "carton", "cardboard", "box"],
    "Plastic Packaging": ["plastic", "poly", "stretch", "bubble", "wrap"],
    "Freight & Logistics": ["freight", "transport", "shipping", "courier", "logistics"],
    "Metal & Steel": ["steel", "metal", "aluminium", "aluminum", "iron"],
    "Office Supplies": ["paper", "pen", "stationery", "toner"],
}


def _classify(desc: str):
    d = (desc or "").lower()
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


# ---------- from the AI dev's structure.py (prompt/output shape changed) ----------

def parse_object(raw):
    if not isinstance(raw, str) or not raw.strip():
        raise ValueError("The model response text is empty.")
    cleaned = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL).strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```$", "", cleaned).strip()
    try:
        obj = json.loads(cleaned)
    except json.JSONDecodeError:
        first, last = cleaned.find("{"), cleaned.rfind("}")
        if first == -1 or last <= first:
            raise ValueError(f"No JSON object in model text: {raw[:500]!r}")
        obj = json.loads(cleaned[first:last + 1])
    if not isinstance(obj, dict):
        raise ValueError("The JSON response is not an object.")
    return obj


def call_ollama(text, json_mode):
    payload = {
        "model": MODEL,
        "prompt": PROMPT + "\n\nINVOICE TEXT:\n" + text + "\n\nReturn the JSON object now.",
        "think": False,
        "stream": False,
        "options": {"temperature": 0, "num_predict": 1500, "num_ctx": 4096},
        "keep_alive": "5m",
    }
    if json_mode:
        payload["format"] = "json"
    resp = requests.post(OLLAMA_URL, json=payload, timeout=300)
    if not resp.ok:
        raise RuntimeError(f"Ollama HTTP {resp.status_code}: {resp.text[:800]}")
    data = resp.json()
    if data.get("error"):
        raise RuntimeError(f"Ollama reported an error: {data['error']}")
    generated = data.get("response")
    if not isinstance(generated, str) or not generated.strip():
        raise ValueError("Ollama returned an empty generated-text field.")
    return generated


def ollama_available() -> bool:
    """False if USE_OLLAMA=0 or the Ollama server doesn't answer within 2s (instant fallback, no long waits)."""
    if os.getenv("USE_OLLAMA", "1") == "0":
        return False
    try:
        return requests.get(OLLAMA_URL.rsplit("/api/", 1)[0], timeout=2).ok
    except Exception:
        return False


def structure_text(text: str) -> list:
    """Raw invoice text -> list of item dicts. JSON mode first, then one retry without it."""
    text = text[:MAX_CHARS]
    try:
        obj = parse_object(call_ollama(text, json_mode=True))
    except (ValueError, json.JSONDecodeError):
        obj = parse_object(call_ollama(text, json_mode=False))
    items = obj.get("items")
    if not isinstance(items, list):
        raise ValueError("Model JSON has no 'items' list.")
    return items


# ---------- conversion to the backend's required format ----------

def _num(v, default=0.0):
    """'Rs 1,20,000' / '₹24.50' / 5000 -> float."""
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str):
        cleaned = re.sub(r"[^\d.\-]", "", v)
        try:
            return float(cleaned)
        except ValueError:
            return default
    return default


def _normalise(item: dict, invoice_id, default_supplier="") -> dict | None:
    desc = str(item.get("description") or "").strip()
    if not desc:
        return None
    qty, price, total = _num(item.get("quantity")), _num(item.get("unit_price")), _num(item.get("total_amount"))
    if not total and qty and price:
        total = qty * price
    if not price and qty and total:
        price = total / qty
    cat, conf = _classify(desc)
    return {"invoice_id": invoice_id, "supplier_name": str(item.get("supplier_name") or default_supplier or "Unknown"),
            "description": desc, "quantity": qty, "unit": str(item.get("unit") or ""), "unit_price": price,
            "total_amount": total, "date": str(item.get("date") or ""), "category": cat, "confidence": conf}


def _parse_csv(text: str):
    rows = list(csv.DictReader(io.StringIO(text)))
    if rows and "description" in {k.strip().lower() for k in rows[0] if k}:
        out = []
        for r in rows:
            r = {k.strip().lower(): v for k, v in r.items() if k}
            out.append({"supplier_name": r.get("supplier_name") or r.get("supplier"), "description": r.get("description"),
                        "quantity": r.get("quantity"), "unit": r.get("unit"), "unit_price": r.get("unit_price"),
                        "total_amount": r.get("total_amount"), "date": r.get("date")})
        return out
    return None


def run_workflow(state: dict) -> dict:
    final, notes = [], state.setdefault("missing_data_requests", [])
    llm_ok = ollama_available()
    for doc in state.get("raw_documents", []):
        inv_id, text = doc["invoice_id"], doc["text"]          # <- raw text arrives here
        raw_items = None
        try:
            raw_items = _parse_csv(text)                       # structured file: no LLM needed
            if raw_items is None and llm_ok:
                raw_items = structure_text(text)               # PDF text: Ollama structures it
        except Exception as e:
            notes.append(f"Could not extract items from {doc.get('filename')}: {e}")
        items = [n for n in (_normalise(i, inv_id) for i in (raw_items or [])) if n]
        if not items:
            notes.append(f"SIMULATED: used demo placeholder items for {doc.get('filename')} "
                         f"({'Ollama not running' if not llm_ok else 'extraction failed'}).")
            items = [n for n in (_normalise(i, inv_id) for i in demo_items()) if n]
        final.extend(items)
    state["extracted_items"] = final
    state["classified_items"] = final
    return state
