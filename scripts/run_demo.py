"""Corre el pipeline completo contra los 18 emails de Fase 1 — de un tirón.

Esto es tu prueba de humo antes de grabar el video: valida que el agente
extrae, resuelve SKU, decide y redacta correctamente en los 18 casos que
ya diseñamos para cubrir las 3 bandas de escalamiento + los casos especiales
(ambigüedad, multi-producto, reorder, precio de competencia).

Costo real: ~18 llamadas a qwen-flash (extracción) + hasta 18 a qwen-plus
(redacción, solo si no quedó en needs_clarification) = unos centavos.

Uso:
    python -m scripts.run_demo
Salida:
    data/demo_results.json   (no se versiona, es un artefacto de corrida)
    resumen impreso en consola
"""
import json
from pathlib import Path

from app.agent import pipeline

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def main() -> None:
    emails = json.loads((DATA_DIR / "emails.json").read_text(encoding="utf-8"))

    results = []
    print("=" * 70)
    print("  TradePilot — corrida de demo sobre 18 emails")
    print("=" * 70)

    for e in emails:
        buyer_email = f"{e['name'].lower().replace(' ', '.')}@example.com"
        print(f"\n[{e['email_id']}] {e['name']} ({e['lang']}/{e['country']}) — {e['subject']}")
        result = pipeline.process_email(
            email_id=e["email_id"],
            buyer_name=e["name"],
            buyer_email=buyer_email,
            subject=e["subject"],
            body=e["body"],
        )
        results.append(result.model_dump())

        if result.status == "error":
            print(f"  ✗ ERROR: {result.error}")
        elif result.status == "needs_clarification":
            reasons = [li.clarification_reason for li in result.line_items if li.needs_clarification]
            print(f"  ⚠ needs_clarification: {reasons}")
        else:
            band = result.decision.band if result.decision else "?"
            price = result.decision.final_unit_price_usd if result.decision else None
            print(f"  ✓ status={result.status}  band={band}  precio_final=${price}")

    out_path = DATA_DIR / "demo_results.json"
    out_path.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")

    print("\n" + "=" * 70)
    print("Resumen")
    print("=" * 70)
    by_status: dict[str, int] = {}
    by_band: dict[str, int] = {}
    for r in results:
        by_status[r["status"]] = by_status.get(r["status"], 0) + 1
        if r.get("decision"):
            b = r["decision"]["band"]
            by_band[b] = by_band.get(b, 0) + 1

    print("Por status:", by_status)
    print("Por banda de decisión:", by_band)
    print(f"\nResultados completos en: {out_path.relative_to(DATA_DIR.parent)}")


if __name__ == "__main__":
    main()
