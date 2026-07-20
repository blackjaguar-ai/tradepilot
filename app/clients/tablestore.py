"""Cliente Alibaba Cloud Tablestore (OTS).

Aquí vivirán las tablas `catalog` (particionada por proveedor) y `buyer_memory`.
En Fase 0 solo necesitamos: conectar, listar tablas y poder crear una tabla
en modo on-demand (sin throughput reservado = sin costo fijo).
"""
from tablestore import (
    OTSClient,
    TableMeta,
    TableOptions,
    ReservedThroughput,
    CapacityUnit,
)

from app.config import get_settings


class TablestoreClient:
    def __init__(self) -> None:
        s = get_settings()
        self._client = OTSClient(
            s.tablestore_endpoint,
            s.tablestore_access_key_id,
            s.tablestore_access_key_secret,
            s.tablestore_instance,
        )

    def list_tables(self) -> list[str]:
        return list(self._client.list_table())

    def ensure_table(self, name: str, pk_schema: list[tuple]) -> bool:
        """Crea la tabla si no existe. Throughput reservado = 0 (on-demand),
        para no generar costo fijo. pk_schema: [(col, tipo), ...].

        Devuelve True si la creó, False si ya existía.
        """
        if name in self.list_tables():
            return False
        table_meta = TableMeta(name, pk_schema)
        # 0/0 reservado => facturación bajo demanda, sin costo por estar creada
        reserved = ReservedThroughput(CapacityUnit(0, 0))
        table_options = TableOptions()
        self._client.create_table(table_meta, table_options, reserved)
        return True

    @property
    def raw(self) -> OTSClient:
        """Acceso directo al SDK para put_row/get_row/get_range en fases siguientes."""
        return self._client

    # ── helpers genéricos para el agente (Fase 2) ──────────────────────
    def put_item(self, table: str, pk: dict, attrs: dict) -> None:
        """Inserta/actualiza una fila. pk debe respetar el orden del schema de la tabla.
        Los valores None se omiten: Tablestore es un wide-column store, "sin valor" se
        representa NO escribiendo la columna, no mandando null (el SDK lo rechaza).
        """
        from tablestore import Row, Condition, RowExistenceExpectation

        clean_attrs = {k: v for k, v in attrs.items() if v is not None}
        row = Row(list(pk.items()), list(clean_attrs.items()))
        self._client.put_row(table, row, Condition(RowExistenceExpectation.IGNORE))

    def get_item(self, table: str, pk: dict) -> dict | None:
        """Lee una fila por su primary key exacta. None si no existe."""
        _, row, _ = self._client.get_row(table, list(pk.items()), max_version=1)
        if row is None:
            return None
        out = {k: v for k, v, _ in row.attribute_columns}
        out.update({k: v for k, v in row.primary_key})
        return out

    def get_range_by_partition(self, table: str, fixed_pk: dict, range_field: str) -> list[dict]:
        """Lee todas las filas que comparten fixed_pk, variando range_field.
        Ej: fixed_pk={"seller_id": "seller_a"}, range_field="sku_id"
            -> todas las filas del catálogo de seller_a.
        """
        from tablestore import Direction, INF_MIN, INF_MAX

        start = list(fixed_pk.items()) + [(range_field, INF_MIN)]
        end = list(fixed_pk.items()) + [(range_field, INF_MAX)]
        results: list[dict] = []
        while True:
            _, next_start, rows, _ = self._client.get_range(
                table, Direction.FORWARD, start, end, limit=200, max_version=1
            )
            for row in rows:
                item = {k: v for k, v, _ in row.attribute_columns}
                item.update({k: v for k, v in row.primary_key})
                results.append(item)
            if not next_start:
                break
            start = next_start
        return results


_ots: TablestoreClient | None = None


def get_tablestore() -> TablestoreClient:
    global _ots
    if _ots is None:
        _ots = TablestoreClient()
    return _ots
