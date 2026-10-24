# Green Procurement Copilot: Frontend

React + Vite + Tailwind + Recharts. Needs Node 18+ (Node 20 recommended).

## Run

```bash
cd frontend
npm install
cp .env.example .env      # Windows PowerShell: copy .env.example .env
npm run dev               # opens at http://localhost:5173
```

## Two modes (edit `.env`, then restart `npm run dev`)

| `VITE_USE_MOCK` | What happens |
|---|---|
| `true`  | Fake data from `src/api/mock.js`. No backend needed. |
| `false` | Real calls to FastAPI at http://localhost:8000 through the Vite proxy (`/api/*`). |

## Where things live

- `src/api/`: every network call (client.js, index.js) and the fake data (mock.js)
- `src/pages/`: one file per screen
- `src/components/`: Badge, Layout, ui (Spinner, ErrorBox, StatCard, Async...)
- `src/hooks/useAsync.js`: loading / error / data helper

## Endpoints this frontend expects (confirm with backend)

POST /upload, POST /upload/sample, GET /lines, PATCH /lines/{id}, GET /hotspots,
GET /suppliers/{line_id}, POST /scenario, GET /recommendation/{line_id},
POST /approve, GET /trace, GET /report?line_id=...
