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
