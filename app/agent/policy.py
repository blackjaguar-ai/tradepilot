"""Política de negociación — determinística, auditable, sin LLM.

Esta es la decisión de negocio más importante del sistema y por eso NO se
la delegamos a un modelo de lenguaje: los descuentos son dinero real, y un
LLM puede alucinar un número. Qwen se usa para leer al comprador y para
redactar la respuesta — nunca para decidir cuánto descuento se aprueba.

Bandas (definidas en la arquitectura del proyecto):
  0–8%   descuento solicitado -> autopilot        (se aprueba sin intervención)
  8–15%  descuento solicitado -> soft_review        (se responde, se marca para auditoría)
  >15%   descuento solicitado -> human_approval      (se bloquea hasta que un humano decida)
"""
from app.agent.schemas import Decision

AUTOPILOT_MAX_PCT = 8.0
SOFT_REVIEW_MAX_PCT = 15.0


def _effective_discount_pct(
    requested_discount_pct: float | None,
    list_price: float | None,
    competitor_price_mentioned_usd: float | None,
) -> tuple[float | None, str]:
    """Determina el % de descuento efectivo a evaluar, y de dónde salió.
    Si el comprador no pide un % pero cita un precio de la competencia,
    ese precio se traduce a un % de descuento implícito — es la misma
    señal de negociación, solo que expresada distinto.
    """
    if requested_discount_pct is not None:
        return requested_discount_pct, "solicitado explícitamente por el comprador"
    if competitor_price_mentioned_usd is not None and list_price:
        implied = round((list_price - competitor_price_mentioned_usd) / list_price * 100, 2)
        return implied, f"inferido de precio de competencia citado (${competitor_price_mentioned_usd})"
    return None, "sin solicitud de descuento"


def decide(
    list_price: float | None,
    requested_discount_pct: float | None,
    competitor_price_mentioned_usd: float | None = None,
    market: dict | None = None,
) -> Decision:
    if list_price is None:
        return Decision(
            band="blocked",
            requested_discount_pct=requested_discount_pct,
            approved_discount_pct=0.0,
            final_unit_price_usd=None,
            requires_human_approval=True,
            reasoning="No se pudo resolver el SKU contra el catálogo; no hay precio de lista para decidir.",
        )

    effective_pct, source = _effective_discount_pct(
        requested_discount_pct, list_price, competitor_price_mentioned_usd
    )

    if effective_pct is None:
        return Decision(
            band="no_discount",
            requested_discount_pct=None,
            approved_discount_pct=0.0,
            final_unit_price_usd=round(list_price, 2),
            requires_human_approval=False,
            reasoning="Sin solicitud de descuento; se cotiza a precio de lista.",
        )

    market_note = ""
    if market and market.get("avg"):
        market_note = f" Referencia de mercado (competencia): promedio ${market['avg']}, rango ${market['min']}-${market['max']}."

    if effective_pct <= 0:
        return Decision(
            band="no_discount",
            requested_discount_pct=effective_pct,
            approved_discount_pct=0.0,
            final_unit_price_usd=round(list_price, 2),
            requires_human_approval=False,
            reasoning=f"Descuento {source} es {effective_pct}% (≤0), se cotiza a precio de lista.{market_note}",
        )

    if effective_pct <= AUTOPILOT_MAX_PCT:
        final_price = round(list_price * (1 - effective_pct / 100), 2)
        return Decision(
            band="autopilot",
            requested_discount_pct=effective_pct,
            approved_discount_pct=effective_pct,
            final_unit_price_usd=final_price,
            requires_human_approval=False,
            reasoning=f"Descuento {source} ({effective_pct}%) está dentro de la banda autopilot "
                      f"(≤{AUTOPILOT_MAX_PCT}%). Aprobado automáticamente.{market_note}",
        )

    if effective_pct <= SOFT_REVIEW_MAX_PCT:
        final_price = round(list_price * (1 - effective_pct / 100), 2)
        return Decision(
            band="soft_review",
            requested_discount_pct=effective_pct,
            approved_discount_pct=effective_pct,
            final_unit_price_usd=final_price,
            requires_human_approval=False,
            reasoning=f"Descuento {source} ({effective_pct}%) está en banda soft_review "
                      f"({AUTOPILOT_MAX_PCT}-{SOFT_REVIEW_MAX_PCT}%). Se responde automáticamente "
                      f"pero queda marcado para auditoría posterior.{market_note}",
        )

    # >15%: bloqueado hasta aprobación humana
    return Decision(
        band="human_approval",
        requested_discount_pct=effective_pct,
        approved_discount_pct=0.0,
        final_unit_price_usd=None,
        requires_human_approval=True,
        reasoning=f"Descuento {source} ({effective_pct}%) supera el máximo autogestionable "
                  f"({SOFT_REVIEW_MAX_PCT}%). Requiere aprobación humana antes de responder.{market_note}",
    )
