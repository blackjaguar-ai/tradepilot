"""Limpia el estado operativo acumulado durante desarrollo — antes de Fase 4.

Borra TODO el contenido de approvals, buyer_memory y processed_emails
(residuo de las corridas de prueba de run_demo.py / run_scan_demo.py).
NO toca el catálogo por defecto — usa --reset-catalog si además quieres
devolver los precios a su valor original de Fase 1 (el repricing real ya
los modificó en Tablestore, lo cual está bien y es la prueba de que
funciona, pero para una demo predecible puede convenir arrancar limpio).

Uso:
    python -m scripts.reset_runtime_data                # limpia colas y memoria
    python -m scripts.reset_runtime_data --reset-catalog # además re-siembra precios originales
"""
import sys

from tablestore import INF_MAX, INF_MIN, Condition, Direction, Row, RowExistenceExpectation

from app.clients.tablestore import get_tablestore


def _wipe_table(ots, table: str, pk_field: str) -> int:
    client = ots.raw
    condition = Condition(RowExistenceExpectation.IGNORE)
    start = [(pk_field, INF_MIN)]
    end = [(pk_field, INF_MAX)]
    count = 0
    while True:
        _, next_start, rows, _ = client.get_range(table, Direction.FORWARD, start, end, limit=200)
        for row in rows:
            pk = dict(row.primary_key)
            client.delete_row(table, Row(list(pk.items())), condition)
            count += 1
        if not next_start:
            break
        start = next_start
    return count


def main() -> None:
    ots = get_tablestore()

    print("Limpiando tablas operativas (approvals, buyer_memory, processed_emails)...")
    n1 = _wipe_table(ots, "approvals", "approval_id")
    print(f"  approvals: {n1} filas borradas")
    n2 = _wipe_table(ots, "buyer_memory", "buyer_email")
    print(f"  buyer_memory: {n2} filas borradas")
    n3 = _wipe_table(ots, "processed_emails", "email_id")
    print(f"  processed_emails: {n3} filas borradas")

    if "--reset-catalog" in sys.argv:
        print("\nRe-sembrando catálogo a precios originales de Fase 1...")
        import scripts.seed_tablestore as seed
        seed.main()

    print("\n✓ Estado operativo limpio. Corre run_demo.py y run_scan_demo.py de nuevo para una demo fresca.")


if __name__ == "__main__":
    main()
