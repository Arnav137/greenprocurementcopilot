# Green Procurement Copilot - Backend

## Run (from inside backend/)
```bash
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
python -m seed.seed               # loads categories, emission factors, supplier options
uvicorn app.main:app --reload --port 8000
```
API docs (the contract for the frontend): http://localhost:8000/docs  |  Base URL: http://localhost:8000/api

If you change models.py: delete app.db, then re-run the seed.

## Endpoints
| Method | Path | Notes |
|---|---|---|
| POST | /api/invoices/upload | multipart, field name `files`, pdf/csv/xlsx |
| GET | /api/invoices | list + status |
| POST | /api/analysis/run | returns `run_id`; runs in background |
| GET | /api/analysis/{run_id} | `status` queued/running/done/failed, `current_step`. Poll every 2s |
| GET | /api/line-items | extracted + classified items with CO2e |
| GET | /api/hotspots | `by_category` and `by_supplier` (chart data) |
| GET | /api/categories | categories + emission factors |
| GET | /api/suppliers/alternatives?category_id= | supplier comparison rows |
| GET | /api/recommendations, /{id} | options, assumptions, evidence, missing_data, draft_email |
| POST | /api/recommendations/{id}/scenario | `{"alternative_id": 2, "volume_share": 0.6}` (use `options[].alternative_id`) |
| POST | /api/recommendations/{id}/approve or /reject | `{"comment": "...", "actor": "..."}` (body optional) |
| GET | /api/recommendations/{id}/report | PDF. Returns 403 until approved |
| GET | /api/audit-logs | audit trail |
| POST | /api/demo/load | FALLBACK: loads pre-baked demo data without uploads or AI |

There is deliberately no send-email endpoint. The draft email is text only (human-in-the-loop).

## Demo flow
upload `sample_data/sample_invoice.csv` -> POST /analysis/run -> poll -> hotspots -> recommendations -> scenario -> approve -> report.

## For the AI dev
Replace the stub in `app/integrations/ai_workflow.py`. Keep `run_workflow(state: dict) -> dict`.
The docstring at the top of that file is the exact input/output contract.
Only `classified_items` is required. `recommendation` text fields are optional and fall back to generated defaults.
Category names must match: Corrugated Packaging, Plastic Packaging, Freight & Logistics, Metal & Steel, Office Supplies, Other.

## Notes
- Emission factors are MOCK values (see seed/seed.py); all results are estimates, not audited.
- Run status is in memory, so it resets on server restart (fine for the demo).
