# TradePilot — Dashboard (Phase 4)

Operations console for TradePilot: approvals queue (quote / reprice / reorder), activity
manifest, and a live catalog view — all reading from the real backend on Alibaba Cloud
Function Compute + Tablestore.

Design: port control tower / customs manifest. The "stamp" (`.stamp`) marks every decision
— autopilot, review, or held — like a real customs seal.

## Architecture

```
Browser → tradepilot.blackjaguar.dev (Nginx, TLS)
              → tradepilot_frontend container (Next.js, internal port 3000)
                  → /api/proxy/*  (server-side, no CORS)
                      → Function Compute (Alibaba Cloud) — the real backend
```

The browser never calls the Function Compute URL directly — everything goes through
Next.js's `/api/proxy/*` routes, which run on the server (Node), not in the browser. That's
how we avoid needing to configure CORS on the FastAPI backend.

## Local deploy (test before pushing to the VPS)

```bash
npm install
cp .env.example .env   # confirm BACKEND_URL points to your real FC deployment
npm run build
npm start
# -> http://localhost:3000
```

## Deploy on the VPS — 3 steps, in order

### Step 1 — upload the project

```bash
mkdir -p /opt/black/tradepilot/web
# copy this folder's contents there (rsync, scp, git clone, whatever you use)
cd /opt/black/tradepilot/web
cp .env.example .env
nano .env   # confirm BACKEND_URL
docker compose up -d --build
```

Confirm the container is running and on the right network:
```bash
docker ps | grep tradepilot_frontend
docker network inspect escai-network | grep tradepilot_frontend
```

### Step 2 — Nginx, STEP A (before the certificate)

Copy `nginx-for-vps/tradepilot.conf.STEP_A` to:
```
/opt/shared/web/nginx/conf.d/tradepilot.conf
```

```bash
docker exec escai-nginx nginx -t          # validate the config before reloading
docker exec escai-nginx nginx -s reload
cd /opt/shared/web
docker compose run --rm certbot certonly --webroot -w /var/www/certbot -d tradepilot.blackjaguar.dev
```

Confirm certbot finished successfully (look for "Successfully received certificate").

### Step 3 — Nginx, STEP B (with the certificate issued)

Replace the CONTENTS of `/opt/shared/web/nginx/conf.d/tradepilot.conf` with
`nginx-for-vps/tradepilot.conf.STEP_B` (which already includes the 443 block + proxy_pass).

```bash
docker exec escai-nginx nginx -t
docker exec escai-nginx nginx -s reload
```

### Final check

```bash
curl -I https://tradepilot.blackjaguar.dev
```

Should return `200 OK`. Open `https://tradepilot.blackjaguar.dev` in a browser — you
should see the dashboard with real data from the catalog, activity, and pending approvals.

## Environment variables

| Variable | What it is |
|---|---|
| `BACKEND_URL` | Public URL of your Function Compute deployment (the one `s info` gave you) |

## Non-negotiable security notes

- **Do NOT** push `certbot/conf/` (TLS private keys) to any public Git repo.
- This project's `.env` has no sensitive secrets (`BACKEND_URL` is public, not a
  credential), but it's still in `.gitignore` out of habit.
