"""Orquestador del agente — el hero flow completo.

email crudo
  -> extract_email()      Qwen-flash, structured output       (¿qué pide?)
  -> resolve_line_items()  Python puro, catálogo + anti-RAG     (¿qué SKU es?)
  -> decide()               Python puro, política de descuento   (¿cuánto se aprueba?)
  -> draft_reply()          Qwen-plus, prosa en idioma del comprador  (¿qué se le contesta?)
  -> persist                Tablestore: memoria de comprador + cola de aprobación si aplica
"""
import hashlib
import json

from app.agent import catalog, policy, store
from app.agent.schemas import AgentResult, Decision, ExtractedEmail, ProductRequest, ResolvedLineItem
from app.clients.qwen import get_qwen

SELLER_ID = "seller_a"  # el vendedor cuyo agente estamos construyendo


def _idempotency_key(buyer_email: str, subject: str, body: str) -> str:
    """Hash del CONTENIDO real del email, no de su email_id.
    email_id es una etiqueta que puede reasignarse a contenido distinto
    (nos pasó en desarrollo); el hash de contenido nunca miente sobre si
    dos emails son 'el mismo' o no — eso es lo que de verdad define un duplicado.
    """
    raw = f"{buyer_email}|{subject}|{body}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:24]

EXTRACT_SYSTEM_PROMPT_TEMPLATE = """Eres un extractor de datos para un agente de ventas B2B cross-border.
Lee el email de un comprador y devuelve SOLO un JSON con este schema exacto, sin texto adicional:

{{
  "language": "código ISO 639-1, ej: es, en, zh, fr, de, pt, ar",
  "intent": "quote_request | negotiation | reorder | ambiguous_product | multi_product | other",
  "products": [
    {{"product_line_query": "nombre de producto mencionado", "variant_query": "ver regla de vocabulario abajo, o null", "quantity": numero_entero}}
  ],
  "discount_requested_pct": numero o null,
  "competitor_price_mentioned_usd": numero o null,
  "is_recurring_buyer_signal": true o false
}}

Vocabulario de variantes VÁLIDAS de este vendedor (colores, capacidades, tallas, modelos de enchufe):
{variant_vocab}

Regla CRÍTICA de "variant_query": el comprador puede mencionar la variante en CUALQUIER idioma
(ej: "blanco", "玫瑰金色", "Schwarz", "الأزرق الداكن", "noires"). Tu trabajo es traducir/mapear esa
mención a la etiqueta EXACTA del vocabulario de arriba que mejor corresponda semánticamente
(ej: "blanco" -> "White", "玫瑰金色" -> "Rose Gold", "Schwarz" -> "Black", "الأزرق الداكن" -> "Navy Blue").
Usa exactamente el texto de la etiqueta del vocabulario, no lo tradusco tú de otra forma.
Si el comprador no menciona variante, o la menciona pero no puedes mapearla con confianza a NINGUNA
etiqueta del vocabulario, deja "variant_query" en null — NUNCA devuelvas el texto original sin mapear.

Otras reglas:
- "intent"="reorder" si el comprador menciona repetir un pedido anterior ("same as last time", "como la última vez", etc.)
- "intent"="ambiguous_product" si menciona un producto sin especificar variante Y ese producto tiene variantes obvias que faltan.
- "intent"="multi_product" si pide más de un producto distinto en el mismo email.
- Si el comprador no pide descuento explícito, "discount_requested_pct" es null.
- Si el comprador cita un precio de otro proveedor/competencia, ponlo en "competitor_price_mentioned_usd".
- NUNCA inventes cantidades: si no se menciona, usa 1.
"""

REPLY_SYSTEM_PROMPT = """Eres el representante de ventas de {seller_name}, un fabricante chino de
electrónica de consumo (audífonos, cargadores, accesorios) que exporta a compradores B2B internacionales.

Te doy la decisión YA TOMADA (precio final, si hay descuento, si necesita aprobación). Tu único trabajo
es REDACTAR la respuesta al comprador en su idioma ({language}), profesional, cálida pero directa,
sin inventar condiciones que no te di. Si el caso requiere aprobación humana, dile que estás revisando
su solicitud especial y le responderás en breve — NO le des un precio final todavía.
Responde SOLO con el texto del email, sin asunto, sin explicaciones adicionales.
"""


def _variant_vocabulary() -> str:
    items = catalog.load_catalog(SELLER_ID)
    vocab = sorted({item["variant"] for item in items})
    return ", ".join(vocab)


def extract_email(subject: str, body: str) -> ExtractedEmail:
    qwen = get_qwen()
    system_prompt = EXTRACT_SYSTEM_PROMPT_TEMPLATE.format(variant_vocab=_variant_vocabulary())
    raw = qwen.raw(
        model=qwen.model_fast,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Asunto: {subject}\n\nCuerpo:\n{body}"},
        ],
        response_format={"type": "json_object"},
        temperature=0,
    )
    content = raw.choices[0].message.content or "{}"
    data = json.loads(content)
    return ExtractedEmail(**data)


def resolve_line_items(products: list[ProductRequest]) -> list[ResolvedLineItem]:
    resolved = []
    for req in products:
        candidates = catalog.find_product_candidates(SELLER_ID, req.product_line_query)
        item, needs_clarif, variant_names = catalog.resolve_variant(candidates, req.variant_query)

        if item is None:
            resolved.append(ResolvedLineItem(
                quantity=req.quantity,
                needs_clarification=needs_clarif or not candidates,
                clarification_reason=(
                    "El comprador no especificó variante y hay varias posibles."
                    if needs_clarif else "No se encontró ninguna línea de producto que coincida."
                ),
                candidate_variants=variant_names,
            ))
            continue

        market = catalog.market_benchmark(item["product_line"])
        resolved.append(ResolvedLineItem(
            sku_id=item["sku_id"],
            product_line=item["product_line"],
            variant=item["variant"],
            quantity=req.quantity,
            list_unit_price_usd=item["unit_price_usd"],
            market_min_usd=market["min"],
            market_max_usd=market["max"],
        ))
    return resolved


def draft_reply(seller_name: str, language: str, decision: Decision, line_items: list[ResolvedLineItem]) -> str:
    qwen = get_qwen()
    context = {
        "decision": decision.model_dump(),
        "line_items": [li.model_dump() for li in line_items],
    }
    system = REPLY_SYSTEM_PROMPT.format(seller_name=seller_name, language=language)
    return qwen.smart(
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": json.dumps(context, ensure_ascii=False)},
        ],
        temperature=0.4,
    )


def process_email(email_id: str, buyer_name: str, buyer_email: str, subject: str, body: str) -> AgentResult:
    # idempotencia: la clave es un hash del CONTENIDO, no el email_id (ver _idempotency_key).
    # Esto evita reprocesar un duplicado real Y evita servir un resultado cacheado
    # viejo si el contenido del email cambió mientras el email_id se reutilizó.
    idem_key = _idempotency_key(buyer_email, subject, body)
    cached = store.get_processed_result(idem_key)
    if cached is not None:
        return AgentResult(**cached)

    result = _run_pipeline(idem_key, email_id, buyer_name, buyer_email, subject, body)
    store.save_processed_result(idem_key, result.model_dump())
    return result


def _run_pipeline(idem_key: str, email_id: str, buyer_name: str, buyer_email: str, subject: str, body: str) -> AgentResult:
    try:
        extracted = extract_email(subject, body)
    except Exception as exc:  # noqa: BLE001
        return AgentResult(
            email_id=email_id, buyer_name=buyer_name, language="unknown",
            extracted=ExtractedEmail(language="unknown", intent="other"),
            line_items=[], decision=None, reply_draft=None,
            status="error", error=f"extract_email falló: {exc}",
        )

    line_items = resolve_line_items(extracted.products)

    if any(li.needs_clarification for li in line_items) or not line_items:
        return AgentResult(
            email_id=email_id, buyer_name=buyer_name, language=extracted.language,
            extracted=extracted, line_items=line_items, decision=None, reply_draft=None,
            status="needs_clarification",
        )

    # tomamos el primer line item para la decisión de descuento (MVP: 1 producto dominante por email)
    primary = line_items[0]
    market = {"min": primary.market_min_usd, "max": primary.market_max_usd, "avg": None}
    if primary.market_min_usd and primary.market_max_usd:
        market["avg"] = round((primary.market_min_usd + primary.market_max_usd) / 2, 2)

    decision = policy.decide(
        list_price=primary.list_unit_price_usd,
        requested_discount_pct=extracted.discount_requested_pct,
        competitor_price_mentioned_usd=extracted.competitor_price_mentioned_usd,
        market=market,
    )

    seller_name = "Shenzhen Aurora Audio Co."
    reply = draft_reply(seller_name, extracted.language, decision, line_items)

    status = "pending_approval" if decision.requires_human_approval else "sent"

    if status == "pending_approval":
        store.enqueue_approval(f"{idem_key}-approval", {
            "kind": "quote",
            "email_id": email_id,
            "buyer_name": buyer_name,
            "buyer_email": buyer_email,
            "language": extracted.language,
            "product_line": primary.product_line,
            "variant": primary.variant,
            "quantity": primary.quantity,
            "list_price": primary.list_unit_price_usd,
            "requested_discount_pct": decision.requested_discount_pct,
            "reasoning": decision.reasoning,
            "draft_reply": reply,
        })

    store.save_buyer_memory(buyer_email, {
        "buyer_name": buyer_name,
        "last_email_id": email_id,
        "last_product_line": primary.product_line,
        "last_variant": primary.variant,
        "last_quantity": primary.quantity,
        "last_unit_price_usd": decision.final_unit_price_usd,
    })

    return AgentResult(
        email_id=email_id, buyer_name=buyer_name, language=extracted.language,
        extracted=extracted, line_items=line_items, decision=decision,
        reply_draft=reply, status=status,
    )
