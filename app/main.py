"""TradePilot — API principal.

En Fase 0 exponemos solo health checks para verificar que el deploy a
Function Compute funciona end-to-end antes de meter lógica del agente.
Los endpoints del agente (ingest de email, aprobación humana) llegan en Fase 3-4.
"""
from fastapi import FastAPI

app = FastAPI(title="TradePilot", version="0.1.0")


@app.get("/health")
def health():
    """Liveness. No toca dependencias externas. FC usa esto para saber que vive."""
    return {"status": "ok", "service": "tradepilot"}


@app.get("/ready")
def ready():
    """Readiness. Confirma que la config carga sin romper. No gasta tokens ni CU."""
    try:
        from app.config import get_settings

        s = get_settings()
        return {
            "status": "ready",
            "region": s.aliyun_region,
            "qwen_model_fast": s.qwen_model_fast,
            "qwen_model_smart": s.qwen_model_smart,
            "tablestore_instance": s.tablestore_instance,
        }
    except Exception as exc:  # noqa: BLE001
        return {"status": "config_error", "detail": str(exc)}


@app.get("/")
def root():
    return {"service": "tradepilot", "docs": "/docs", "health": "/health"}


# ── Agente (Fase 2) ─────────────────────────────────────────────────
from pydantic import BaseModel

from app.agent import pipeline, store


class EmailIn(BaseModel):
    email_id: str
    buyer_name: str
    buyer_email: str
    subject: str
    body: str


@app.post("/agent/process-email")
def process_email(payload: EmailIn):
    """Corre el pipeline completo sobre un email y devuelve el resultado."""
    result = pipeline.process_email(
        email_id=payload.email_id,
        buyer_name=payload.buyer_name,
        buyer_email=payload.buyer_email,
        subject=payload.subject,
        body=payload.body,
    )
    return result.model_dump()


@app.get("/agent/approvals")
def list_approvals():
    """Cola de aprobación humana: descuentos >15% pendientes de decisión."""
    return {"pending": store.list_pending_approvals()}


class ApprovalDecision(BaseModel):
    approved: bool
    approved_discount_pct: float | None = None


@app.post("/agent/approvals/{approval_id}/decision")
def resolve_approval(approval_id: str, payload: ApprovalDecision):
    store.resolve_approval(approval_id, payload.approved, payload.approved_discount_pct)
    return {"approval_id": approval_id, "status": "approved" if payload.approved else "rejected"}
