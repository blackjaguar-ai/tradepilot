"""Catálogo y benchmark de mercado.

Fuente de verdad: Tablestore (tabla `catalog`, PK compuesta seller_id+sku_id).
Fallback: los JSON de data/ generados en Fase 1 — así puedes desarrollar y
probar el pipeline sin gastar CU de Tablestore ni depender de la red en
cada iteración. En producción (Function Compute) siempre pega a Tablestore.
"""
import json
import re
from functools import lru_cache
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
CATALOG_TABLE = "catalog"


def _load_local(seller_id: str) -> list[dict]:
    path = DATA_DIR / f"catalog_{seller_id}.json"
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


@lru_cache(maxsize=8)
def load_catalog(seller_id: str) -> tuple[dict, ...]:
    """Devuelve el catálogo de un vendedor. Intenta Tablestore, cae a JSON local.
    Cacheado en memoria por proceso — el catálogo no cambia dentro de una misma
    invocación de Function Compute, no tiene sentido re-consultarlo por cada email.
    """
    try:
        from app.clients.tablestore import get_tablestore

        rows = get_tablestore().get_range_by_partition(
            CATALOG_TABLE, {"seller_id": seller_id}, "sku_id"
        )
        if rows:
            return tuple(rows)
    except Exception:
        pass  # sin credenciales válidas, tabla no sembrada aún, o sin red: cae a local
    return tuple(_load_local(seller_id))


def _normalize(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def find_product_candidates(seller_id: str, query: str) -> list[dict]:
    """Busca líneas de producto por solapamiento de tokens contra product_line.
    Esto es deliberadamente un matching simple, NO un vector search — con el
    diseño anti-RAG del catálogo (mismo nombre en 3 vendedores, 5 variantes
    por línea), un match de texto solo te da candidatos; la resolución final
    depende de seller_id (ya fijo, porque sabemos a quién llegó el email) y
    de si el comprador especificó variante.
    """
    catalog = load_catalog(seller_id)
    q_tokens = set(_normalize(query).split())
    if not q_tokens:
        return []

    scored = []
    for item in catalog:
        line_tokens = set(_normalize(item["product_line"]).split())
        overlap = len(q_tokens & line_tokens)
        if overlap > 0:
            scored.append((overlap, item))
    scored.sort(key=lambda x: -x[0])
    # agrupar por product_line (todas las variantes de la mejor línea encontrada)
    if not scored:
        return []
    best_line = scored[0][1]["product_line"]
    return [item for item in catalog if item["product_line"] == best_line]


def resolve_variant(candidates: list[dict], variant_query: str | None) -> tuple[dict | None, bool, list[str]]:
    """Dado un grupo de variantes de la misma línea, intenta resolver a UNA sola.
    Devuelve (item_resuelto_o_None, necesita_aclaracion, nombres_de_variantes_candidatas).
    """
    if not candidates:
        return None, False, []
    if len(candidates) == 1:
        return candidates[0], False, []

    if variant_query:
        vq = _normalize(variant_query)
        if vq:  # guarda: una normalización vacía (ej. texto no-latino que se coló sin traducir)
            # NUNCA debe tratarse como "coincide con todo" — eso fue el bug original.
            for item in candidates:
                iv = _normalize(item["variant"])
                if iv and (vq in iv or iv in vq):
                    return item, False, []

    # más de una variante posible y no se pudo desambiguar -> pedir aclaración
    return None, True, [c["variant"] for c in candidates]


def update_price(seller_id: str, sku_id: str, new_price: float) -> None:
    """Escribe el nuevo precio a Tablestore y limpia el caché en memoria.

    IMPORTANTE: put_row en Tablestore reemplaza la fila COMPLETA, no hace merge
    parcial (a diferencia de un UPDATE de SQL). Por eso leemos la fila existente
    primero y solo pisamos el campo de precio — si no, perderíamos product_line,
    variant, stock_qty y el resto de columnas del SKU.

    El caché (@lru_cache en load_catalog) también se limpia: si no, el resto
    del proceso seguiría viendo el precio viejo hasta reiniciar.
    """
    from app.clients.tablestore import get_tablestore

    ots = get_tablestore()
    pk = {"seller_id": seller_id, "sku_id": sku_id}
    existing = ots.get_item(CATALOG_TABLE, pk) or {}
    ots.put_item(CATALOG_TABLE, pk, {**existing, "unit_price_usd": new_price})
    load_catalog.cache_clear()


def market_benchmark(product_line: str, competitor_seller_ids: tuple[str, ...] = ("seller_b", "seller_c")) -> dict:
    """Precio min/max/prom de la misma línea de producto en catálogos competidores.
    Esta es la señal de mercado real que alimenta la negociación — no un número inventado.
    """
    prices: list[float] = []
    for sid in competitor_seller_ids:
        for item in load_catalog(sid):
            if item["product_line"] == product_line:
                prices.append(item["unit_price_usd"])
    if not prices:
        return {"min": None, "max": None, "avg": None, "n": 0}
    return {
        "min": round(min(prices), 2),
        "max": round(max(prices), 2),
        "avg": round(sum(prices) / len(prices), 2),
        "n": len(prices),
    }
