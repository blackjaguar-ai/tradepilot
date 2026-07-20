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


# ── Ingesta real de email (Fase 3) ──────────────────────────────────
import uuid
from email.utils import parseaddr

from fastapi import Request


@app.post("/webhook/email")
async def webhook_email(request: Request):
    """Endpoint de ingesta real, compatible con el formato de SendGrid Inbound Parse
    (y similares: Mailgun Routes, Postmark inbound). Estos servicios convierten un
    email real que llega a un dominio en un POST multipart/form-data con campos
    'from', 'subject', 'text'. Esto es lo que conectarías a un buzón de verdad —
    a diferencia de /agent/process-email (Fase 2), que espera JSON ya estructurado
    para pruebas.
    """
    form = await request.form()
    from_raw = str(form.get("from", ""))
    subject = str(form.get("subject", ""))
    body = str(form.get("text") or form.get("html") or "")

    buyer_name, buyer_email = parseaddr(from_raw)
    if not buyer_email:
        return {"status": "error", "error": "No se pudo parsear el remitente ('from')"}

    result = pipeline.process_email(
        email_id=f"webhook-{uuid.uuid4().hex[:10]}",
        buyer_name=buyer_name or buyer_email,
        buyer_email=buyer_email,
        subject=subject,
        body=body,
    )
    return result.model_dump()


# ── Repricing y reorden (Fase 3, subflujos 2 y 3) ───────────────────
from app.agent import reorder as reorder_module
from app.agent import repricing as repricing_module


@app.post("/agent/scan/repricing")
def scan_repricing():
    """Dispara el escaneo de repricing contra todo el catálogo de seller_a.
    Pensado para invocarse desde un trigger de tiempo (cron) en Function Compute,
    o manualmente/vía cron externo durante el hackathon.
    """
    results = repricing_module.run_repricing_scan()
    return {
        "scanned": len(results),
        "applied_autopilot": sum(1 for r in results if r.band == "autopilot"),
        "sent_to_approval": sum(1 for r in results if r.band == "human_approval"),
        "no_change": sum(1 for r in results if r.band == "no_change"),
        "results": [r.model_dump() for r in results],
    }


@app.post("/agent/scan/reorder")
def scan_reorder():
    """Dispara el escaneo de inventario bajo contra todo el catálogo de seller_a."""
    results = reorder_module.run_reorder_scan()
    return {
        "flagged_for_reorder": len(results),
        "results": [r.model_dump() for r in results],
    }


# ── Endpoints de lectura para el dashboard (Fase 4) ─────────────────
from app.agent import catalog as catalog_module


@app.get("/catalog/{seller_id}")
def get_catalog(seller_id: str):
    """Catálogo completo de un vendedor — para la vista de tabla del dashboard."""
    items = catalog_module.load_catalog(seller_id)
    return {"seller_id": seller_id, "count": len(items), "items": list(items)}


@app.get("/agent/activity")
def get_activity(limit: int = 50):
    """Últimos emails procesados (cualquier banda) — feed de actividad del dashboard."""
    items = store.list_processed_emails(limit=limit)
    return {"count": len(items), "items": items}
