"""Corre los escaneos de repricing y reorder contra el catálogo real de Tablestore.

Prueba de humo de Fase 3, igual que run_demo.py lo es de Fase 2. Corre esto
DESPUÉS de haber corrido run_demo.py al menos una vez (para tener aprobaciones
de cotización ya en la cola y ver que las 3 colas conviven bien).

Uso:
    python -m scripts.run_scan_demo
"""
from app.agent import reorder, repricing


def main() -> None:
    print("=" * 70)
    print("  TradePilot — escaneo de repricing")
    print("=" * 70)
    reprice_results = repricing.run_repricing_scan()
    for r in reprice_results:
        if r.band == "no_change":
            continue
        tag = "APLICADO" if r.applied else "PENDIENTE APROBACIÓN"
        print(f"  [{tag}] {r.sku_id} {r.product_line} ({r.variant}): "
              f"${r.current_price_usd} -> ${r.recommended_price_usd} "
              f"(desviación {r.deviation_pct}%)")

    no_change = sum(1 for r in reprice_results if r.band == "no_change")
    autopilot = sum(1 for r in reprice_results if r.band == "autopilot")
    human = sum(1 for r in reprice_results if r.band == "human_approval")
    print(f"\nResumen repricing: {len(reprice_results)} SKUs escaneados | "
          f"{no_change} sin cambio | {autopilot} auto-aplicados | {human} a aprobación")

    print("\n" + "=" * 70)
    print("  TradePilot — escaneo de reorden de inventario")
    print("=" * 70)
    reorder_results = reorder.run_reorder_scan()
    for r in reorder_results:
        print(f"  [PENDIENTE APROBACIÓN] {r.sku_id} {r.product_line} ({r.variant}): "
              f"stock={r.current_stock} -> producir {r.recommended_qty}")
        if r.draft_memo:
            print(f"      memo: {r.draft_memo[:100]}...")

    print(f"\nResumen reorder: {len(reorder_results)} SKUs bajo el umbral de {reorder.REORDER_THRESHOLD} unidades")

    print("\n" + "=" * 70)
    print("Cola de aprobaciones pendientes (las 3 colas conviven en una sola tabla)")
    print("=" * 70)
    from app.agent import store
    pending = store.list_pending_approvals()
    by_kind: dict[str, int] = {}
    for p in pending:
        k = p.get("kind", "unknown")
        by_kind[k] = by_kind.get(k, 0) + 1
    print(f"Total pendientes: {len(pending)}  |  por tipo: {by_kind}")


if __name__ == "__main__":
    main()
