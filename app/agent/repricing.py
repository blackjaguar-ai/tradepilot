"""Repricing automático — subflujo 2.

Compara el precio de cada SKU de seller_a contra el promedio de mercado
(competidores B/C) y decide si ajustar. Misma filosofía de bandas que la
negociación de descuentos — no por casualidad: es el mismo agente core,
la misma disciplina de "las decisiones de dinero no las toma el LLM".

Bandas:
  |desviación| <= 3%    -> no_change      (ya está bien alineado, no se toca)
  3% < |desv| <= 10%     -> autopilot       (se ajusta solo, se aplica al catálogo)
  |desviación| > 10%     -> human_approval  (se propone, pero NO se aplica sin humano)
"""
from app.agent import catalog, store
from app.agent.schemas import RepriceDecision

SELLER_ID = "seller_a"
NO_CHANGE_MAX_PCT = 3.0
AUTOPILOT_MAX_PCT = 10.0


def decide_reprice(sku: dict, market: dict) -> RepriceDecision:
    current = sku["unit_price_usd"]
    avg = market.get("avg")

    if avg is None:
        return RepriceDecision(
            sku_id=sku["sku_id"], product_line=sku["product_line"], variant=sku["variant"],
            current_price_usd=current, market_avg_usd=None, deviation_pct=None,
            band="no_change", recommended_price_usd=None, applied=False,
            reasoning="Sin datos de mercado (ningún competidor vende esta línea). No se puede evaluar.",
        )

    deviation_pct = round((current - avg) / avg * 100, 2)
    abs_dev = abs(deviation_pct)

    if abs_dev <= NO_CHANGE_MAX_PCT:
        return RepriceDecision(
            sku_id=sku["sku_id"], product_line=sku["product_line"], variant=sku["variant"],
            current_price_usd=current, market_avg_usd=avg, deviation_pct=deviation_pct,
            band="no_change", recommended_price_usd=current, applied=False,
            reasoning=f"Precio ya alineado con mercado (desviación {deviation_pct}%, dentro de ±{NO_CHANGE_MAX_PCT}%). Sin cambios.",
        )

    if abs_dev <= AUTOPILOT_MAX_PCT:
        return RepriceDecision(
            sku_id=sku["sku_id"], product_line=sku["product_line"], variant=sku["variant"],
            current_price_usd=current, market_avg_usd=avg, deviation_pct=deviation_pct,
            band="autopilot", recommended_price_usd=avg, applied=False,
            reasoning=f"Desviación de {deviation_pct}% respecto al mercado, dentro de banda autopilot "
                      f"(≤{AUTOPILOT_MAX_PCT}%). Se realinea automáticamente al promedio de mercado (${avg}).",
        )

    return RepriceDecision(
        sku_id=sku["sku_id"], product_line=sku["product_line"], variant=sku["variant"],
        current_price_usd=current, market_avg_usd=avg, deviation_pct=deviation_pct,
        band="human_approval", recommended_price_usd=avg, applied=False,
        reasoning=f"Desviación de {deviation_pct}% supera el máximo autogestionable (±{AUTOPILOT_MAX_PCT}%). "
                  f"Cambio de precio propuesto a ${avg}, pero requiere aprobación humana antes de aplicarse.",
    )


def run_repricing_scan(seller_id: str = SELLER_ID) -> list[RepriceDecision]:
    """Recorre todo el catálogo, decide, aplica lo que es autopilot, encola lo que no."""
    results = []
    for sku in catalog.load_catalog(seller_id):
        market = catalog.market_benchmark(sku["product_line"])
        decision = decide_reprice(sku, market)

        if decision.band == "autopilot":
            catalog.update_price(seller_id, sku["sku_id"], decision.recommended_price_usd)
            decision.applied = True
        elif decision.band == "human_approval":
            approval_id = f"reprice-{sku['sku_id']}"
            existing = store.get_approval(approval_id)
            same_proposal_already_queued = (
                existing is not None
                and existing.get("recommended_price_usd") == decision.recommended_price_usd
            )
            if not same_proposal_already_queued:
                store.enqueue_approval(approval_id, {
                    "kind": "reprice",
                    "sku_id": sku["sku_id"],
                    "product_line": sku["product_line"],
                    "variant": sku["variant"],
                    "current_price_usd": decision.current_price_usd,
                    "recommended_price_usd": decision.recommended_price_usd,
                    "deviation_pct": decision.deviation_pct,
                    "reasoning": decision.reasoning,
                })

        results.append(decision)
    return results
