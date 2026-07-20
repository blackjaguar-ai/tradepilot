"""Generador de datos sintéticos — Fase 1.

Genera 3 catálogos de electrónica de consumo (audífonos, cargadores,
accesorios) y 18 emails de compradores multilingües.

Diseño ANTI-RAG (a propósito, no es descuido):
  1. 80% de las líneas de producto (32/40) se repiten en los 3 catálogos con
     el MISMO nombre pero SKU/precio/stock distintos por vendedor. Un RAG
     ingenuo que busque por texto va a encontrar 3 candidatos igual de
     válidos — el agente tiene que resolver por CONTEXTO (a qué vendedor
     llegó el email), no por similitud semántica.
  2. Dentro del catálogo de un mismo vendedor, una línea de producto tiene
     hasta 5 variantes (color/capacidad) con nombres casi idénticos. Si el
     comprador no especifica variante, el agente debe pedir aclaración en
     vez de adivinar — eso es lo que separa un demo de un producto real.
  3. 20% (8/40) son líneas EXCLUSIVAS por vendedor, para que el catálogo
     tenga identidad propia y no sea un copy-paste literal.

Uso:
    python -m scripts.generate_fixtures
Salida:
    data/catalog_seller_a.json   <- el vendedor cuyo agente construimos
    data/catalog_seller_b.json   <- competidor (señal de mercado)
    data/catalog_seller_c.json   <- competidor (señal de mercado)
    data/emails.json             <- 18 emails multilingües de compradores
"""
import json
import random
from pathlib import Path

random.seed(42)  # determinístico: mismo output cada vez que corras esto

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

SELLERS = {
    "seller_a": {"name": "Shenzhen Aurora Audio Co.", "you": True},
    "seller_b": {"name": "Guangzhou Vantek Electronics", "you": False},
    "seller_c": {"name": "Yiwu Brightline Trading", "you": False},
}

# 8 categorías x 5 variantes = 40 líneas de producto por catálogo.
# Cada tupla: (línea de producto, [variantes de color/capacidad])
CATEGORIES = [
    ("TWS Earbuds AeroBuds X2", ["Black", "White", "Navy Blue", "Rose Gold", "Graphite"]),
    ("Over-Ear Headphones SoundMax H7", ["Black", "Silver", "Midnight Blue", "Beige", "Red"]),
    ("Bluetooth Speaker BoomCube Mini", ["Black", "Teal", "Orange", "White", "Camo"]),
    ("GaN Wall Charger PowerNode 65W", ["US Plug", "EU Plug", "UK Plug", "AU Plug", "Universal"]),
    ("Power Bank VoltCell 20000mAh", ["Black", "White", "Slate Grey", "Blue", "Pink"]),
    ("USB-C Cable FlexLink 100W", ["1m", "2m", "0.5m", "3m Braided", "1m Braided"]),
    ("Phone Case ShieldFlex Clear", ["iPhone 16", "iPhone 16 Pro", "Galaxy S26", "Galaxy S26+", "Pixel 10"]),
    ("Screen Protector GlassGuard 9H", ["iPhone 16", "iPhone 16 Pro", "Galaxy S26", "Galaxy S26+", "Pixel 10"]),
]

# Líneas exclusivas por vendedor (20%: ~2-3 por vendedor, 8 en total)
EXCLUSIVE_LINES = {
    "seller_a": [
        ("TWS Earbuds AeroBuds X2 Pro ANC", ["Black", "White", "Titanium"]),
    ],
    "seller_b": [
        ("Wireless Charging Pad OrbitDock 15W", ["Black", "White", "Wood Grain"]),
    ],
    "seller_c": [
        ("Car Charger DriveVolt 45W Dual-Port", ["Black", "Silver", "Red"]),
    ],
}

BASE_PRICE_RANGE = {
    "TWS Earbuds AeroBuds X2": (8.5, 14.0),
    "TWS Earbuds AeroBuds X2 Pro ANC": (16.0, 22.0),
    "Over-Ear Headphones SoundMax H7": (12.0, 19.0),
    "Bluetooth Speaker BoomCube Mini": (9.0, 15.0),
    "GaN Wall Charger PowerNode 65W": (6.5, 11.0),
    "Power Bank VoltCell 20000mAh": (11.0, 18.0),
    "USB-C Cable FlexLink 100W": (1.8, 3.5),
    "Phone Case ShieldFlex Clear": (1.2, 2.8),
    "Screen Protector GlassGuard 9H": (0.8, 1.9),
    "Wireless Charging Pad OrbitDock 15W": (7.0, 12.0),
    "Car Charger DriveVolt 45W Dual-Port": (4.5, 8.0),
}


def price_for(seller_id: str, product_line: str) -> float:
    """Precio determinístico pero distinto por vendedor (señal de mercado real)."""
    lo, hi = BASE_PRICE_RANGE[product_line]
    # cada vendedor tiene un sesgo de precio consistente, no aleatorio puro
    bias = {"seller_a": 0.0, "seller_b": 0.06, "seller_c": -0.08}[seller_id]
    base = lo + (hi - lo) * random.random()
    return round(base * (1 + bias), 2)


def build_catalog(seller_id: str) -> list[dict]:
    items = []
    counter = 1
    for product_line, variants in CATEGORIES:
        for variant in variants:
            sku_id = f"{seller_id.upper()}-{counter:03d}"
            items.append({
                "sku_id": sku_id,
                "seller_id": seller_id,
                "seller_name": SELLERS[seller_id]["name"],
                "product_line": product_line,
                "variant": variant,
                "unit_price_usd": price_for(seller_id, product_line),
                "moq": random.choice([50, 100, 100, 200, 300]),
                "stock_qty": random.choice([120, 340, 560, 80, 1200, 45, 900]),
                "lead_time_days": random.choice([7, 10, 12, 15]),
            })
            counter += 1
    for product_line, variants in EXCLUSIVE_LINES.get(seller_id, []):
        for variant in variants:
            sku_id = f"{seller_id.upper()}-{counter:03d}"
            items.append({
                "sku_id": sku_id,
                "seller_id": seller_id,
                "seller_name": SELLERS[seller_id]["name"],
                "product_line": product_line,
                "variant": variant,
                "unit_price_usd": price_for(seller_id, product_line),
                "moq": random.choice([50, 100, 200]),
                "stock_qty": random.choice([60, 150, 400]),
                "lead_time_days": random.choice([10, 14, 18]),
            })
            counter += 1
    return items


# ─────────────────────────────────────────────────────────────
# Emails de compradores — multilingües, distintos niveles de negociación
# Umbrales de escalamiento que deben probarse: 0-8% autopiloto,
# 8-15% revisión suave, >15% aprobación humana obligatoria.
# ─────────────────────────────────────────────────────────────
EMAILS = [
    dict(lang="en", country="US", name="Marcus Webb",
         subject="Quote request — AeroBuds X2",
         body="Hi, I'm looking to buy TWS earbuds, the AeroBuds X2 model, "
              "in black. Can you send me a quote for 150 units? What's your best price?",
         discount_ask_pct=0, note="hero flow: petición directa, sin regateo"),
    dict(lang="es", country="MX", name="Camila Reyes",
         subject="Cotización audífonos inalámbricos",
         body="Buenas, necesito cotizar los audífonos AeroBuds X2 en color blanco, "
              "unas 200 unidades. ¿Manejan algún descuento por volumen?",
         discount_ask_pct=5, note="descuento leve, dentro de autopiloto"),
    dict(lang="zh", country="CN", name="Li Wei",
         subject="询价 - 蓝牙耳机",
         body="你好，我想采购 AeroBuds X2 蓝牙耳机，玫瑰金色，数量300个。"
              "如果订购300个，价格能优惠多少？",
         discount_ask_pct=7, note="autopiloto, borde superior de la banda"),
    dict(lang="fr", country="FR", name="Élodie Marchand",
         subject="Demande de devis — chargeurs GaN",
         body="Bonjour, je souhaite commander le chargeur PowerNode 65W, "
              "prise EU, 100 unités. Pouvez-vous m'envoyer un devis avec le meilleur prix possible ?",
         discount_ask_pct=3, note="autopiloto"),
    dict(lang="de", country="DE", name="Jonas Richter",
         subject="Anfrage: Power Bank VoltCell",
         body="Hallo, ich interessiere mich für die VoltCell 20000mAh Powerbank in Schwarz. "
              "Wir bräuchten 250 Stück. Ist ein Rabatt von 12% bei dieser Menge möglich?",
         discount_ask_pct=12, note="revisión suave, 8-15%"),
    dict(lang="pt", country="BR", name="Rafael Souza",
         subject="Orçamento — fones TWS",
         body="Olá, gostaria de um orçamento para os fones AeroBuds X2, cor grafite, "
              "quantidade de 180 unidades. Vocês conseguem um desconto de 10%?",
         discount_ask_pct=10, note="revisión suave"),
    dict(lang="en", country="GB", name="Priya Shah",
         subject="Bulk order — screen protectors",
         body="We'd like to order GlassGuard 9H screen protectors for iPhone 16 Pro, "
              "500 units. Given the volume, we're expecting a 20% discount off list price.",
         discount_ask_pct=20, note="aprobación humana obligatoria, >15%"),
    dict(lang="es", country="AR", name="Tomás Ferreyra",
         subject="Pedido grande - parlantes bluetooth",
         body="Hola, quiero pedir 400 unidades del parlante BoomCube Mini en color negro. "
              "Necesitamos un 18% de descuento para que el negocio nos cierre, si no compramos a otro proveedor.",
         discount_ask_pct=18, note="aprobación humana + presión de competencia"),
    dict(lang="en", country="CA", name="Daniel Osei",
         subject="Which earbuds do you have?",
         body="Hi, I saw your AeroBuds listing but I'm not sure which version — "
              "is there a noise cancelling one? Can you tell me the difference and pricing?",
         discount_ask_pct=None, note="AMBIGUO a propósito: X2 estándar vs X2 Pro ANC, "
                                      "el agente debe desambiguar antes de cotizar"),
    dict(lang="ar", country="AE", name="Yousef Al-Amin",
         subject="طلب عرض سعر - سماعات لاسلكية",
         body="مرحباً، أرغب بشراء سماعات AeroBuds X2 باللون الأزرق الداكن، الكمية 120 قطعة. "
              "هل يمكن الحصول على أفضل سعر؟",
         discount_ask_pct=4, note="autopiloto, prueba multilingüe RTL"),
    dict(lang="en", country="AU", name="Chloe Bennett",
         subject="Cable pricing",
         body="Need a quote on the USB-C FlexLink 100W cable, 2m length, 1000 units. "
              "What's your lead time and best unit price?",
         discount_ask_pct=0, note="hero flow, sin negociación, volumen alto"),
    dict(lang="es", country="CO", name="Valentina Prieto",
         subject="Consulta fundas para celular",
         body="Buenos días, ¿tienen fundas transparentes para iPhone 16? "
              "Necesito 300 unidades, ¿cuál es el precio y si hacen descuento?",
         discount_ask_pct=6, note="autopiloto"),
    dict(lang="zh", country="SG", name="Chen Jiaming",
         subject="询价 - 车载充电器",
         body="你好，请问 DriveVolt 45W 车载充电器有货吗？我们需要150个，"
              "如果长期合作能给多少折扣？",
         discount_ask_pct=9, note="revisión suave, producto exclusivo del vendedor C "
                                  "(chequea que el agente NO lo confunda con catálogo propio)"),
    dict(lang="en", country="NG", name="Adaeze Okafor",
         subject="Competitor is offering lower price",
         body="I got a quote from another supplier for the VoltCell power bank at $9.50/unit "
              "for 300 units. Can you match or beat that price?",
         discount_ask_pct=None, note="negociación basada en precio de competencia — "
                                      "prueba directa del uso de datos B/C como señal de mercado"),
    dict(lang="de", country="AT", name="Sophie Lang",
         subject="Anfrage Kopfhörer SoundMax",
         body="Guten Tag, ich benötige 100 Stück SoundMax H7 Kopfhörer in Silber. "
              "Bitte senden Sie mir ein Angebot.",
         discount_ask_pct=0, note="hero flow simple"),
    dict(lang="pt", country="PT", name="Miguel Andrade",
         subject="Pedido protetores de ecrã",
         body="Boa tarde, preciso de 250 protetores de ecrã GlassGuard para Galaxy S26. "
              "Podem fazer 15% de desconto?",
         discount_ask_pct=15, note="límite exacto de la banda de revisión suave"),
    dict(lang="fr", country="BE", name="Antoine Dubois",
         subject="Devis powerbank + câbles",
         body="Bonjour, je voudrais un devis combiné : 150 powerbanks VoltCell noires "
              "et 150 câbles FlexLink 1m. Meilleur prix pour les deux ensemble ?",
         discount_ask_pct=None, note="multi-producto en un solo email — "
                                      "prueba de extracción de más de un SKU"),
    dict(lang="en", country="IE", name="Grace O'Sullivan",
         subject="Reorder — same as last time",
         body="Hi, we'd like to reorder the AeroBuds X2 in Black, same quantity as our "
              "usual order (200 units). No need to requote if price is stable.",
         discount_ask_pct=None, note="dispara el trigger de reorder/memoria de comprador "
                                      "recurrente (subflujo 3)"),
]


def main() -> None:
    DATA_DIR.mkdir(exist_ok=True)

    catalogs = {sid: build_catalog(sid) for sid in SELLERS}
    for sid, items in catalogs.items():
        path = DATA_DIR / f"catalog_{sid}.json"
        path.write_text(json.dumps(items, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"✓ {path.relative_to(DATA_DIR.parent)}  ({len(items)} SKUs)")

    emails = []
    for i, e in enumerate(EMAILS, start=1):
        emails.append({"email_id": f"EMAIL-{i:03d}", **e})
    path = DATA_DIR / "emails.json"
    path.write_text(json.dumps(emails, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"✓ {path.relative_to(DATA_DIR.parent)}  ({len(emails)} emails)")

    # resumen de cobertura de escalamiento, para que confirmes que las 3
    # bandas de descuento (autopiloto / revisión suave / aprobación humana)
    # están representadas antes de construir la lógica del agente
    bands = {"autopilot(0-8%)": 0, "soft_review(8-15%)": 0, "human_approval(>15%)": 0, "no_discount_or_ambiguous": 0}
    for e in EMAILS:
        p = e["discount_ask_pct"]
        if p is None:
            bands["no_discount_or_ambiguous"] += 1
        elif p <= 8:
            bands["autopilot(0-8%)"] += 1
        elif p <= 15:
            bands["soft_review(8-15%)"] += 1
        else:
            bands["human_approval(>15%)"] += 1
    print("\nCobertura de bandas de escalamiento:")
    for k, v in bands.items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
