# TradePilot — Dashboard (Fase 4)

Consola de operaciones para TradePilot: cola de aprobaciones (cotización / reprecio / reorden),
manifiesto de actividad, y catálogo en vivo — todo leyendo del backend real en Alibaba Cloud
Function Compute + Tablestore.

Diseño: torre de control portuaria / manifiesto de aduana. El "sello" (`.stamp`) marca cada
decisión — autopiloto, revisión, o retenido — como si fuera un timbre de aduana real.

## Arquitectura

```
Navegador → tradepilot.blackjaguar.dev (Nginx, TLS)
              → contenedor tradepilot_frontend (Next.js, puerto 3000 interno)
                  → /api/proxy/*  (server-side, sin CORS)
                      → Function Compute (Alibaba Cloud) — el backend real
```

El navegador NUNCA llama directo a la URL de Function Compute — todo pasa por las rutas
`/api/proxy/*` de Next.js, que corren en el servidor (Node), no en el navegador. Así evitamos
tener que configurar CORS en el backend de FastAPI.

## Deploy local (prueba antes de subir al VPS)

```bash
npm install
cp .env.example .env   # y confirma que BACKEND_URL apunta a tu FC real
npm run build
npm start
# -> http://localhost:3000
```

## Deploy en el VPS — 3 pasos, en orden

### Paso 1 — sube el proyecto

```bash
mkdir -p /opt/black/tradepilot/web
# copia todo el contenido de esta carpeta ahí (rsync, scp, git clone, lo que uses)
cd /opt/black/tradepilot/web
cp .env.example .env
nano .env   # confirma BACKEND_URL
docker compose up -d --build
```

Verifica que el contenedor corre y está en la red correcta:
```bash
docker ps | grep tradepilot_frontend
docker network inspect escai-network | grep tradepilot_frontend
```

### Paso 2 — Nginx, PASO A (antes del certificado)

Copia `nginx-for-vps/tradepilot.conf.STEP_A` como:
```
/opt/shared/web/nginx/conf.d/tradepilot.conf
```

```bash
docker exec escai-nginx nginx -t          # valida la config antes de recargar
docker exec escai-nginx nginx -s reload
cd /opt/shared/web
docker compose run --rm certbot certonly --webroot -w /var/www/certbot -d tradepilot.blackjaguar.dev
```

Confirma que certbot terminó con éxito (busca "Successfully received certificate").

### Paso 3 — Nginx, PASO B (con el certificado ya emitido)

Reemplaza el CONTENIDO de `/opt/shared/web/nginx/conf.d/tradepilot.conf` por el de
`nginx-for-vps/tradepilot.conf.STEP_B` (el que ya incluye el bloque 443 + proxy_pass).

```bash
docker exec escai-nginx nginx -t
docker exec escai-nginx nginx -s reload
```

### Verificación final

```bash
curl -I https://tradepilot.blackjaguar.dev
```

Debería responder `200 OK`. Abre `https://tradepilot.blackjaguar.dev` en el navegador — deberías
ver el dashboard con datos reales del catálogo, actividad, y aprobaciones pendientes.

## Variables de entorno

| Variable | Qué es |
|---|---|
| `BACKEND_URL` | URL pública de tu función en Function Compute (la que te dio `s info`) |

## Notas de seguridad no negociables

- **NO** subas `certbot/conf/` (llaves privadas TLS) a ningún repo Git público.
- El `.env` de este proyecto no tiene secretos sensibles (`BACKEND_URL` es pública, no una
  credencial), pero igual está en `.gitignore` por hábito.
