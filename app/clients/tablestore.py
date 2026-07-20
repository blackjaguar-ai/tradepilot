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


_ots: TablestoreClient | None = None


def get_tablestore() -> TablestoreClient:
    global _ots
    if _ots is None:
        _ots = TablestoreClient()
    return _ots
