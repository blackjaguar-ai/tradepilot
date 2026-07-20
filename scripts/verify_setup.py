"""Verificación de setup — checkpoint de Fase 0.

Corre esto ANTES de escribir cualquier lógica del agente. Confirma que:
  1. Todas las variables de entorno están presentes.
  2. La API key de Qwen funciona (llamada mínima real, ~centavos).
  3. Tablestore conecta y podemos listar tablas.

Uso:
    python -m scripts.verify_setup

Si algo sale FAIL, arréglalo antes de avanzar. No sigas a ciegas.
"""
import sys

GREEN = "\033[92m"
RED = "\033[91m"
YEL = "\033[93m"
RESET = "\033[0m"


def ok(msg: str) -> None:
    print(f"{GREEN}✓ PASS{RESET}  {msg}")


def fail(msg: str) -> None:
    print(f"{RED}✗ FAIL{RESET}  {msg}")


def info(msg: str) -> None:
    print(f"{YEL}·{RESET}      {msg}")


def check_env() -> bool:
    print("\n[1/3] Variables de entorno")
    try:
        from app.config import get_settings

        s = get_settings()
    except Exception as exc:  # noqa: BLE001
        fail(f"No se pudo cargar la config: {exc}")
        info("¿Copiaste .env.example a .env y lo rellenaste?")
        return False

    missing = []
    for name, val in [
        ("DASHSCOPE_API_KEY", s.dashscope_api_key),
        ("TABLESTORE_ENDPOINT", s.tablestore_endpoint),
        ("TABLESTORE_INSTANCE", s.tablestore_instance),
        ("TABLESTORE_ACCESS_KEY_ID", s.tablestore_access_key_id),
        ("TABLESTORE_ACCESS_KEY_SECRET", s.tablestore_access_key_secret),
    ]:
        if not val or val.startswith(("sk-xxxx", "LTAI5xxxx", "xxxx")):
            missing.append(name)

    if missing:
        fail(f"Faltan o siguen con placeholder: {', '.join(missing)}")
        return False
    ok("Todas las variables presentes")
    return True


def check_qwen() -> bool:
    print("\n[2/3] Qwen (DashScope OpenAI-compatible)")
    try:
        from app.clients.qwen import get_qwen

        out = get_qwen().fast(
            messages=[{"role": "user", "content": "responde solo: ok"}],
            max_tokens=5,
        )
        ok(f"Qwen respondió: {out.strip()!r}")
        return True
    except Exception as exc:  # noqa: BLE001
        fail(f"Qwen no respondió: {exc}")
        info("Revisa DASHSCOPE_API_KEY y que QWEN_BASE_URL coincida con tu cuenta")
        info("(intl -> dashscope-intl / mainland -> dashscope)")
        return False


def check_tablestore() -> bool:
    print("\n[3/3] Alibaba Cloud Tablestore")
    try:
        from app.clients.tablestore import get_tablestore

        tables = get_tablestore().list_tables()
        ok(f"Tablestore conectó. Tablas actuales: {tables or '(ninguna todavía)'}")
        return True
    except Exception as exc:  # noqa: BLE001
        fail(f"Tablestore no conectó: {exc}")
        info("Revisa el endpoint (https://<instancia>.<region>.ots.aliyuncs.com),")
        info("el nombre de instancia y el AccessKey.")
        return False


def main() -> int:
    print("=" * 55)
    print("  TradePilot — verificación de setup (Fase 0)")
    print("=" * 55)

    results = [check_env(), check_qwen(), check_tablestore()]

    print("\n" + "=" * 55)
    if all(results):
        print(f"{GREEN}TODO VERDE.{RESET} Setup listo. Puedes arrancar Fase 1.")
        return 0
    print(f"{RED}HAY FALLAS.{RESET} Arréglalas antes de seguir.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
