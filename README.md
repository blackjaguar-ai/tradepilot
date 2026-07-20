# TradePilot 🚀

**Copiloto de operaciones cross-border para vendedores del ecosistema Alibaba/AliExpress.**

Lee emails de compradores en cualquier idioma, arma cotizaciones contra el catálogo real del vendedor, negocia usando precios de la competencia como señal de mercado, monitorea precio/inventario y redacta órdenes de compra — pidiendo aprobación humana **solo cuando el riesgo lo amerita**.

> Hackathon: **Global AI Hackathon Series with Qwen Cloud** · Track 4 — Autopilot Agent.

---

## Por qué Qwen (ventaja auténtica, no bolted-on)

1. **Costo-por-token bajo** → volumen alto de decisiones viable en unit economics reales.
2. **Integración nativa con el ecosistema Alibaba** (Tablestore, Function Compute) → foso que GPT/Claude/Gemini no replican.
3. **Multilingüe** → responde en el idioma del email del comprador. Moneda siempre USD.

## Arquitectura: un solo agente core, tres triggers

No son tres sistemas: son tres disparadores alimentando el **mismo** agente Qwen, el **mismo** catálogo (Tablestore), la **misma** memoria y el **mismo** checkpoint humano.

| Subflujo | Trigger | Qué hace |
|---|---|---|
| 1 · Cotización + negociación (hero) | email entrante | parsea, detecta idioma/intención, desambigua producto, cotiza y negocia con datos de B/C |
| 2 · Repricing | cron | ajusta precio dentro de banda ±10%, escala fuera de banda |
| 3 · Reorder / PO | cron | compara venta vs. stock, redacta orden de compra |

**Regla de escalamiento:** 0–8% descuento → autopiloto · 8–15% → revisión suave · >15% → aprobación humana obligatoria.

## Stack

| Capa | Herramienta |
|---|---|
| LLM | Qwen (API OpenAI-compatible vía DashScope) |
| Backend | Python + FastAPI |
| Memoria/DB | Alibaba Cloud Tablestore |
| Deploy | Alibaba Cloud Function Compute (serverless) |
| Frontend | Next.js mínimo (bandeja + panel de aprobación) |

---

## Setup (Fase 0)

```bash
# 1. Entorno
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# 2. Credenciales
cp .env.example .env      # luego rellena .env con tus keys reales

# 3. Verificar que todo conecta (Qwen + Tablestore + env)
python -m scripts.verify_setup

# 4. Levantar la API en local
uvicorn app.main:app --reload
# -> http://127.0.0.1:8000/health   y   /docs
```

## Deploy a Alibaba Cloud Function Compute

```bash
npm install -g @serverless-devs/s   # una vez
s config add                        # configura tu AccessKey de Alibaba Cloud
s deploy                            # despliega usando s.yaml
s info                              # te da la URL pública del trigger HTTP
```

## Estructura

```
tradepilot/
├── app/
│   ├── main.py            # FastAPI (health checks; endpoints del agente en fase 3-4)
│   ├── config.py          # config tipada desde entorno
│   └── clients/
│       ├── qwen.py        # cliente Qwen (fast + smart)
│       └── tablestore.py  # cliente Tablestore (OTS)
├── scripts/
│   └── verify_setup.py    # checkpoint de Fase 0
├── bootstrap              # entrypoint del custom runtime de Function Compute
├── s.yaml                 # descriptor de deploy (Serverless Devs)
├── requirements.txt
├── .env.example
└── LICENSE                # MIT
```

## Licencia

MIT — ver [LICENSE](./LICENSE).
