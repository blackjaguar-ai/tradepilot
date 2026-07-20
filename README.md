# TradePilot 🚀

**Copiloto de operaciones cross-border para vendedores del ecosistema Alibaba/AliExpress.**

Lee emails de compradores en cualquier idioma, arma cotizaciones contra el catálogo real del
vendedor, negocia usando precios de la competencia como señal de mercado, reprecia el catálogo
y detecta inventario bajo — pidiendo aprobación humana **solo cuando el riesgo lo amerita**.

> Hackathon: **Global AI Hackathon Series with Qwen Cloud** · Track 4 — Autopilot Agent.
> Demo en vivo: **https://tradepilot.blackjaguar.dev**

---

## Por qué Qwen (ventaja auténtica, no bolted-on)

1. **Costo-por-token bajo** → volumen alto de decisiones viable en unit economics reales
   (`qwen-flash` para extracción de alto volumen, `qwen-plus` solo para redacción final).
2. **Integración nativa con el ecosistema Alibaba** — Tablestore y Function Compute, no
   servicios de terceros pegados con cinta.
3. **Multilingüe de verdad** — el agente lee y responde en el idioma del comprador (probado en
   7 idiomas: en/es/zh/fr/de/pt/ar), traduciendo incluso nombres de variante contra un
   vocabulario controlado del catálogo.

## La decisión de arquitectura que no negociamos

**El LLM nunca decide cuánto dinero se aprueba.** `qwen-flash` extrae datos, `qwen-plus`
redacta texto — pero el descuento, el nuevo precio, y la cantidad a producir salen de
política Python 100% determinística (`app/agent/policy.py`, `repricing.py`, `reorder.py`).
Un modelo de lenguaje no puede alucinar un descuento que nunca calculó.

## Arquitectura: un solo agente core, tres triggers, un dashboard

```
                    ┌─────────────────────────────────────────┐
                    │      Alibaba Cloud (ap-southeast-1)      │
                    │                                           │
  Email real ──────▶│  Function Compute (FastAPI, custom rt.)  │
  /webhook/email     │    ├─ pipeline.py  (extract→resolve→     │
                     │    │   decide→draft, Qwen-flash+plus)    │
  Cron cada 10min ──▶│    ├─ repricing.py (banda ±10%)          │
  /agent/scan/*       │    └─ reorder.py   (umbral de stock)     │
                     │              │                            │
                     │       Tablestore (catalog, buyer_memory,  │
                     │       approvals, processed_emails)        │
                     └──────────────┬────────────────────────────┘
                                    │ HTTPS (proxy server-side,
                                    │ sin CORS en el backend)
                    ┌───────────────▼────────────────┐
                    │   tradepilot.blackjaguar.dev     │
                    │   Next.js (Docker, VPS propio)   │
                    │   Nginx + Let's Encrypt           │
                    └───────────────────────────────────┘
```

No son tres sistemas: son tres disparadores alimentando el **mismo** agente Qwen, el
**mismo** catálogo (Tablestore), la **misma** memoria y el **mismo** checkpoint humano
(una sola cola de aprobaciones, distinguida por `kind`: `quote` | `reprice` | `reorder`).

| Subflujo | Trigger | Qué hace |
|---|---|---|
| 1 · Cotización + negociación (hero) | email entrante / webhook | parsea, detecta idioma/intención, desambigua producto, cotiza y negocia con datos de B/C |
| 2 · Repricing | cron cada 10 min | ajusta precio dentro de banda ±10%, escala fuera de banda |
| 3 · Reorder / producción | cron cada 10 min | compara stock vs. umbral, redacta memo de producción |

**Bandas de escalamiento** (mismo criterio en los 3 subflujos):

| Banda | Descuento / desviación | Acción |
|---|---|---|
| Autopilot | ≤ 8% (cotización) · ≤ 10% (reprecio) | se aprueba/aplica solo |
| Revisión suave | 8-15% (solo cotización) | se responde, queda marcado para auditoría |
| Retenido | > 15% (cotización) · > 10% (reprecio) · siempre (reorder) | bloqueado hasta tu firma |

## Diseño anti-RAG del catálogo (Fase 1)

80% de las líneas de producto se repiten en los 3 catálogos (vendedor propio + 2
competidores) con el mismo nombre pero SKU/precio distintos. Un RAG por similitud de texto
encuentra 3 candidatos igualmente "relevantes" — el agente resuelve por **contexto real**
(a qué vendedor llegó el email), no por parecido semántico. Dentro del propio catálogo,
una línea de producto tiene hasta 5 variantes con nombres casi idénticos (`iPhone 16` vs
`iPhone 16 Pro`, `Galaxy S26` vs `Galaxy S26+`) — el matching prioriza exacto sobre
substring para no confundir un producto con otro.

## Stack

| Capa | Herramienta |
|---|---|
| LLM | Qwen (`qwen-flash` + `qwen-plus`, API OpenAI-compatible vía Model Studio) |
| Backend | Python + FastAPI, custom runtime en Function Compute |
| Memoria/DB | Alibaba Cloud Tablestore |
| Deploy backend | Alibaba Cloud Function Compute (serverless, escala a 0) |
| Frontend | Next.js 14 (App Router), Docker, VPS propio |
| Proxy/TLS | Nginx + Let's Encrypt (VPS) |

## Estructura del repo

```
tradepilot/
├── app/
│   ├── main.py              # FastAPI: ingesta, scans, lectura para el dashboard
│   ├── config.py             # config tipada desde entorno
│   ├── agent/
│   │   ├── pipeline.py       # orquestador del hero flow (subflujo 1)
│   │   ├── repricing.py      # subflujo 2
│   │   ├── reorder.py        # subflujo 3
│   │   ├── policy.py         # política de descuento — determinística
│   │   ├── catalog.py        # matching anti-RAG + benchmark de mercado
│   │   ├── store.py          # aprobaciones, memoria de comprador, idempotencia
│   │   └── schemas.py        # contratos Pydantic entre etapas
│   └── clients/
│       ├── qwen.py           # cliente Qwen (fast + smart)
│       └── tablestore.py     # cliente Tablestore (OTS)
├── scripts/
│   ├── verify_setup.py       # checkpoint de Fase 0
│   ├── generate_fixtures.py  # genera catálogos + 18 emails de prueba
│   ├── seed_tablestore.py    # siembra Tablestore
│   ├── run_demo.py           # corre los 18 emails de un tirón
│   ├── run_scan_demo.py      # corre repricing + reorder de un tirón
│   └── reset_runtime_data.py # limpia estado operativo (approvals/memoria/caché)
├── data/                     # catálogos y emails generados (Fase 1)
├── web/                      # dashboard Next.js (Fase 4) — ver web/README.md
├── s.template.yaml           # plantilla de deploy (Serverless Devs, sin secretos)
├── bootstrap                 # entrypoint del custom runtime de Function Compute
└── requirements.txt
```

## Setup local

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env      # rellena con tus credenciales reales
python -m scripts.verify_setup     # checkpoint: Qwen + Tablestore + env
python -m scripts.generate_fixtures
python -m scripts.seed_tablestore
python -m scripts.run_demo         # prueba de humo: 18 emails, cubre las 3 bandas
python -m scripts.run_scan_demo    # prueba de humo: repricing + reorder
uvicorn app.main:app --reload
```

## Deploy a Function Compute

El `s.yaml` real se genera desde `s.template.yaml` con `envsubst` — nunca se commitea con
secretos inyectados.

```bash
npm install -g @serverless-devs/s
s config add                                  # tu AccessKey (RAM user, no cuenta principal)

export $(grep -v '^#' .env | xargs)
envsubst < s.template.yaml > s.yaml
s build --use-docker                          # instala requirements.txt en ./python
s deploy
s info                                         # URL pública del trigger HTTP
```

Automatización de repricing/reorder — cron externo en tu propio servidor (no timer
nativo de FC, más simple y confiable):

```bash
*/10 * * * * /ruta/a/scan_cron.sh >> /var/log/tradepilot-cron.log 2>&1
```

## Dashboard (Fase 4)

Ver [`web/README.md`](./web/README.md) para el deploy completo del dashboard en un VPS
propio vía Docker + Nginx + Let's Encrypt.

## Limitaciones conocidas (honestidad, no relleno)

- El endpoint de escaneo (`/agent/scan/*`) es público sin autenticación — aceptable para el
  alcance del hackathon, no para producción real sin agregar auth.
- "Rechazar" en la cola de aprobación solo cambia el estado — no envía automáticamente un
  email de rechazo al comprador.
- El matching de *línea de producto* (no de variante) sigue siendo comparación literal de
  tokens — falla seguro (pide aclaración) cuando el nombre no coincide en otro idioma,
  pero no traduce como sí lo hace el matching de variante.

## Licencia

MIT — ver [LICENSE](./LICENSE).
