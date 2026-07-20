"""Reorden de inventario — subflujo 3.

Recorre el catálogo de seller_a, detecta SKUs con stock bajo el umbral, y
redacta un memo de reposición de producción (Aurora Audio es el fabricante,
así que "reordenar" significa pedir más corrida de producción, no comprarle
a un tercero).

A diferencia de descuentos y repricing, el reorden SIEMPRE requiere
aprobación humana — comprometer capital en producción es un riesgo distinto
al de aprobar un % de descuento, y no vale la pena automatizarlo del todo
en un MVP. Lo que SÍ automatizamos es la detección y la redacción del draft.
"""
from app.agent import catalog, store
from app.agent.schemas import ReorderDecision
from app.clients.qwen import get_qwen

SELLER_ID = "seller_a"
REORDER_THRESHOLD = 150  # unidades; por debajo de esto se recomienda reponer

MEMO_SYSTEM_PROMPT = """Eres el encargado de operaciones de Shenzhen Aurora Audio Co.
Redacta un memo BREVE y profesional (máximo 5 líneas) dirigido al equipo de producción,
solicitando una nueva corrida de fabricación para el SKU indicado. Sé directo: qué producto,
qué variante, cuánto stock queda, cuánto se recomienda producir. Sin relleno.
Responde SOLO con el texto del memo, en español.
"""


def _draft_memo(sku: dict, recommended_qty: int) -> str:
    qwen = get_qwen()
    context = (
        f"Producto: {sku['product_line']} ({sku['variant']})\n"
        f"SKU: {sku['sku_id']}\n"
        f"Stock actual: {sku['stock_qty']} unidades\n"
        f"Cantidad recomendada a producir: {recommended_qty} unidades\n"
    )
    return qwen.smart(
        messages=[
            {"role": "system", "content": MEMO_SYSTEM_PROMPT},
            {"role": "user", "content": context},
        ],
        temperature=0.3,
    )


def decide_reorder(sku: dict) -> ReorderDecision | None:
    """None si el stock está sano y no hace falta reordenar."""
    stock = sku["stock_qty"]
    if stock >= REORDER_THRESHOLD:
        return None

    recommended_qty = sku["moq"] * 2  # reponer a un colchón de 2x el MOQ
    return ReorderDecision(
        sku_id=sku["sku_id"], product_line=sku["product_line"], variant=sku["variant"],
        current_stock=stock, reorder_threshold=REORDER_THRESHOLD,
        recommended_qty=recommended_qty, draft_memo=None,
        reasoning=f"Stock actual ({stock}) por debajo del umbral ({REORDER_THRESHOLD}). "
                  f"Se recomienda producir {recommended_qty} unidades adicionales.",
    )


def run_reorder_scan(seller_id: str = SELLER_ID) -> list[ReorderDecision]:
    results = []
    for sku in catalog.load_catalog(seller_id):
        decision = decide_reorder(sku)
        if decision is None:
            continue

        approval_id = f"reorder-{sku['sku_id']}"
        existing = store.get_approval(approval_id)
        # OJO: el guard compara solo recommended_qty, sin importar el status.
        # Si comparara solo contra "ya resuelta", un cron periódico redactaría
        # el memo con Qwen (gasta tokens reales) en cada corrida mientras la
        # aprobación siga pendiente — que es la mayoría del tiempo.
        same_proposal_already_queued = (
            existing is not None and existing.get("recommended_qty") == decision.recommended_qty
        )
        if same_proposal_already_queued:
            decision.draft_memo = existing.get("draft_memo")
            results.append(decision)
            continue

        memo = _draft_memo(sku, decision.recommended_qty)
        decision.draft_memo = memo

        store.enqueue_approval(approval_id, {
            "kind": "reorder",
            "sku_id": sku["sku_id"],
            "product_line": sku["product_line"],
            "variant": sku["variant"],
            "current_stock": decision.current_stock,
            "recommended_qty": decision.recommended_qty,
            "draft_memo": memo,
            "reasoning": decision.reasoning,
        })
        results.append(decision)
    return results
