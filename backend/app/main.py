from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .database import Base, engine
from . import models  # noqa: F401  (registers tables)
from .routers import invoices, analysis, suppliers, recommendations

Base.metadata.create_all(engine)

app = FastAPI(title="Green Procurement Copilot API")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
for r in (invoices.router, analysis.router, suppliers.router, recommendations.router):
    app.include_router(r, prefix="/api")


@app.get("/")
def health():
    return {"status": "ok", "docs": "/docs"}
