"""Contratos de datos del pipeline del agente.

El flujo es: email crudo -> ExtractedEmail (Qwen-flash, structured output)
-> ResolvedLineItem[] (Python puro, catálogo) -> Decision (Python puro,
política de negocio) -> texto final (Qwen-plus).

Separar esto en etapas tipadas es lo que te permite debuggear cuál parte
falló sin adivinar — y es lo que un juez técnico espera ver en un agente
"production-ready", no un solo prompt gigante que hace de todo.
"""
from pydantic import BaseModel, Field


class ProductRequest(BaseModel):
    """Un producto pedido dentro de un email (puede haber más de uno)."""
    product_line_query: str = Field(..., description="Nombre de producto tal como lo entendió el modelo")
    variant_query: str | None = Field(None, description="Color/capacidad/talla si el comprador la especificó")
    quantity: int = Field(..., description="Cantidad solicitada")


class ExtractedEmail(BaseModel):
    """Salida cruda de qwen-flash al leer el email. Nada de decisiones de negocio aquí."""
    language: str = Field(..., description="Código ISO del idioma detectado, ej: es, en, zh")
    intent: str = Field(
        ...,
        description="quote_request | negotiation | reorder | ambiguous_product | multi_product | other",
    )
    products: list[ProductRequest] = Field(default_factory=list)
    discount_requested_pct: float | None = None
    competitor_price_mentioned_usd: float | None = None
    is_recurring_buyer_signal: bool = Field(
        False, description="True si el comprador menciona 'reorder', 'como la última vez', etc."
    )


class ResolvedLineItem(BaseModel):
    """Un producto ya cruzado contra el catálogo real de seller_a."""
    sku_id: str | None = None
    product_line: str | None = None
    variant: str | None = None
    quantity: int
    list_unit_price_usd: float | None = None
    needs_clarification: bool = False
    clarification_reason: str | None = None
    candidate_variants: list[str] = Field(default_factory=list)
    market_min_usd: float | None = None
    market_max_usd: float | None = None


class Decision(BaseModel):
    """Salida de la política de descuento — 100% determinística, sin LLM."""
    band: str = Field(..., description="autopilot | soft_review | human_approval | no_discount | blocked")
    requested_discount_pct: float | None
    approved_discount_pct: float
    final_unit_price_usd: float | None
    requires_human_approval: bool
    reasoning: str


class AgentResult(BaseModel):
    """Resultado completo de procesar un email: lo que se guarda y lo que se muestra en el demo."""
    email_id: str
    buyer_name: str
    language: str
    extracted: ExtractedEmail
    line_items: list[ResolvedLineItem]
    decision: Decision | None
    reply_draft: str | None
    status: str = Field(..., description="sent | pending_approval | needs_clarification | error")
    error: str | None = None
