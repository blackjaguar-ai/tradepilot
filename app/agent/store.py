"""Persistencia de memoria de comprador y cola de aprobación humana.

Mismo patrón que catalog.py: Tablestore es la fuente de verdad, JSON local
en data/ es el fallback para desarrollo sin gastar CU ni depender de red.

Dos tablas:
  buyer_memory  PK: buyer_email          -> última orden, para detectar reorders
  approvals     PK: approval_id          -> cola de decisiones >15% pendientes de humano
"""
import json
import time
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
BUYER_MEMORY_TABLE = "buyer_memory"
APPROVALS_TABLE = "approvals"
PROCESSED_EMAILS_TABLE = "processed_emails"

_LOCAL_MEMORY_FILE = DATA_DIR / "_runtime_buyer_memory.json"
_LOCAL_APPROVALS_FILE = DATA_DIR / "_runtime_approvals.json"
_LOCAL_PROCESSED_FILE = DATA_DIR / "_runtime_processed_emails.json"


def _read_local(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _write_local(path: Path, data: dict) -> None:
    DATA_DIR.mkdir(exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


# ── memoria de comprador ────────────────────────────────────────────
def save_buyer_memory(buyer_email: str, record: dict) -> None:
    record = {**record, "updated_at": int(time.time())}
    try:
        from app.clients.tablestore import get_tablestore

        get_tablestore().put_item(
            BUYER_MEMORY_TABLE, {"buyer_email": buyer_email}, record
        )
        return
    except Exception:
        pass
    data = _read_local(_LOCAL_MEMORY_FILE)
    data[buyer_email] = record
    _write_local(_LOCAL_MEMORY_FILE, data)


def get_buyer_memory(buyer_email: str) -> dict | None:
    try:
        from app.clients.tablestore import get_tablestore

        item = get_tablestore().get_item(BUYER_MEMORY_TABLE, {"buyer_email": buyer_email})
        if item is not None:
            return item
    except Exception:
        pass
    return _read_local(_LOCAL_MEMORY_FILE).get(buyer_email)


# ── cola de aprobación humana ───────────────────────────────────────
def get_approval(approval_id: str) -> dict | None:
    try:
        from app.clients.tablestore import get_tablestore

        item = get_tablestore().get_item(APPROVALS_TABLE, {"approval_id": approval_id})
        if item is not None:
            return item
    except Exception:
        pass
    data = _read_local(_LOCAL_APPROVALS_FILE)
    return data.get(approval_id)


def enqueue_approval(approval_id: str, record: dict) -> None:
    record = {**record, "status": "pending", "created_at": int(time.time())}
    try:
        from app.clients.tablestore import get_tablestore

        get_tablestore().put_item(APPROVALS_TABLE, {"approval_id": approval_id}, record)
        return
    except Exception:
        pass
    data = _read_local(_LOCAL_APPROVALS_FILE)
    data[approval_id] = record
    _write_local(_LOCAL_APPROVALS_FILE, data)


def list_pending_approvals() -> list[dict]:
    try:
        from app.clients.tablestore import get_tablestore
        from tablestore import Direction, INF_MIN, INF_MAX

        client = get_tablestore().raw
        start = [("approval_id", INF_MIN)]
        end = [("approval_id", INF_MAX)]
        _, _, rows, _ = client.get_range(APPROVALS_TABLE, Direction.FORWARD, start, end, limit=200)
        items = []
        for row in rows:
            item = {k: v for k, v, _ in row.attribute_columns}
            item.update({k: v for k, v in row.primary_key})
            items.append(item)
        if items:
            return [i for i in items if i.get("status") == "pending"]
    except Exception:
        pass
    data = _read_local(_LOCAL_APPROVALS_FILE)
    return [{**v, "approval_id": k} for k, v in data.items() if v.get("status") == "pending"]


def resolve_approval(approval_id: str, approved: bool, approved_discount_pct: float | None = None) -> None:
    status = "approved" if approved else "rejected"
    update = {"status": status, "resolved_at": int(time.time())}
    if approved_discount_pct is not None:
        update["approved_discount_pct"] = approved_discount_pct
    try:
        from app.clients.tablestore import get_tablestore

        client = get_tablestore()
        existing = client.get_item(APPROVALS_TABLE, {"approval_id": approval_id}) or {}
        client.put_item(APPROVALS_TABLE, {"approval_id": approval_id}, {**existing, **update})
        return
    except Exception:
        pass
    data = _read_local(_LOCAL_APPROVALS_FILE)
    if approval_id in data:
        data[approval_id].update(update)
        _write_local(_LOCAL_APPROVALS_FILE, data)


# ── idempotencia: no reprocesar el mismo email dos veces ────────────
# Un email real puede llegar duplicado (retry de webhook, timeout de red).
# Sin esto, reprocesar sobrescribiría una aprobación humana ya resuelta
# de vuelta a "pending" — se perdería la decisión sin que nadie lo note.
def get_processed_result(email_id: str) -> dict | None:
    try:
        from app.clients.tablestore import get_tablestore

        item = get_tablestore().get_item(PROCESSED_EMAILS_TABLE, {"email_id": email_id})
        if item is not None and "result_json" in item:
            return json.loads(item["result_json"])
    except Exception:
        pass
    data = _read_local(_LOCAL_PROCESSED_FILE)
    return data.get(email_id)


def save_processed_result(email_id: str, result: dict) -> None:
    payload = json.dumps(result, ensure_ascii=False)
    try:
        from app.clients.tablestore import get_tablestore

        get_tablestore().put_item(
            PROCESSED_EMAILS_TABLE, {"email_id": email_id},
            {"result_json": payload, "processed_at": int(time.time())},
        )
        return
    except Exception:
        pass
    data = _read_local(_LOCAL_PROCESSED_FILE)
    data[email_id] = result
    _write_local(_LOCAL_PROCESSED_FILE, data)


def list_processed_emails(limit: int = 50) -> list[dict]:
    """Lista los últimos emails procesados — el feed de actividad del dashboard.
    No existía ningún listado hasta ahora, solo lookup por ID individual.
    """
    try:
        from app.clients.tablestore import get_tablestore
        from tablestore import Direction, INF_MAX, INF_MIN

        client = get_tablestore().raw
        start = [("email_id", INF_MIN)]
        end = [("email_id", INF_MAX)]
        items = []
        while True:
            _, next_start, rows, _ = client.get_range(
                PROCESSED_EMAILS_TABLE, Direction.FORWARD, start, end, limit=200
            )
            for row in rows:
                attrs = {k: v for k, v, _ in row.attribute_columns}
                if "result_json" in attrs:
                    result = json.loads(attrs["result_json"])
                    result["_processed_at"] = attrs.get("processed_at")
                    items.append(result)
            if not next_start:
                break
            start = next_start
        items.sort(key=lambda r: r.get("_processed_at") or 0, reverse=True)
        if items:
            return items[:limit]
    except Exception:
        pass
    data = _read_local(_LOCAL_PROCESSED_FILE)
    items = list(data.values())
    return items[:limit]
