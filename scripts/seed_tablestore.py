"""Siembra Tablestore — corre esto UNA VEZ (o cada vez que regeneres los catálogos).

Crea (si no existen) las 3 tablas del agente y carga los catálogos de data/*.json.
Todas las tablas se crean en modo on-demand (throughput reservado 0/0) — no
generan costo fijo por existir, solo pagas por las lecturas/escrituras reales.

Uso:
    python -m scripts.seed_tablestore
"""
import json
from pathlib import Path

from app.clients.tablestore import get_tablestore

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

# El SDK real (tablestore v6.4.8+) NO expone un enum PrimaryKeyType.
# El schema de primary key se define con strings literales: 'STRING' | 'INTEGER' | 'BINARY'.
STRING = "STRING"


def main() -> None:
    ots = get_tablestore()

    print("Creando tablas (si no existen)...")
    created = ots.ensure_table("catalog", [
        ("seller_id", STRING),
        ("sku_id", STRING),
    ])
    print(f"  catalog: {'creada' if created else 'ya existía'}")

    created = ots.ensure_table("buyer_memory", [
        ("buyer_email", STRING),
    ])
    print(f"  buyer_memory: {'creada' if created else 'ya existía'}")

    created = ots.ensure_table("approvals", [
        ("approval_id", STRING),
    ])
    print(f"  approvals: {'creada' if created else 'ya existía'}")

    created = ots.ensure_table("processed_emails", [
        ("email_id", STRING),
    ])
    print(f"  processed_emails: {'creada' if created else 'ya existía'}")

    print("\nSembrando catálogos...")
    total = 0
    for seller_id in ("seller_a", "seller_b", "seller_c"):
        path = DATA_DIR / f"catalog_{seller_id}.json"
        items = json.loads(path.read_text(encoding="utf-8"))
        for item in items:
            pk = {"seller_id": item["seller_id"], "sku_id": item["sku_id"]}
            attrs = {k: v for k, v in item.items() if k not in pk}
            ots.put_item("catalog", pk, attrs)
        print(f"  {seller_id}: {len(items)} SKUs cargados")
        total += len(items)

    print(f"\n✓ Listo. {total} SKUs sembrados en Tablestore.")


if __name__ == "__main__":
    main()
