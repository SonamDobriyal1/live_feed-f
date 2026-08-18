# CP Plus Camera Live Feed + Violence Detection

Live RTSPS feed from CP Plus cameras, YOLOv8 violence classification, and **SMS alerts via Twilio** on detection.

## Deploy (production)

```bash
cp .env.example .env          # set CAMERA_*, SMS_TO, TWILIO_*
pip3 install -r requirements.txt
python3 violence_monitor.py --test-sms
python3 violence_monitor.py     # runs headless if DEPLOY_HEADLESS=true
```

**Docker:** `docker compose up -d --build`

Full guide: **[DEPLOY.md](DEPLOY.md)** · Render: **[RENDER.md](RENDER.md)**

### Render (cloud, no live feed)

Push to GitHub → Render **Background Worker** (Docker) → set env vars in Dashboard.

```yaml
# render.yaml included — Blueprint deploy
CAMERA_IP, CAMERA_USER, CAMERA_PASS, SMS_TO, TWILIO_* in Render env
```

See **[RENDER.md](RENDER.md)** for step-by-step.

## Quick Start (local viewing)

```bash
pip3 install -r requirements.txt
python3 probe.py
python3 live_feed.py
```

## Scripts

| Script | Purpose |
|--------|---------|
| `violence_monitor.py` | **Production** — live ML + SMS alerts |
| `live_feed.py` | Auto-detect stream method |
| `rtsp_viewer.py` | RTSPS viewer |
| `probe.py` | Port / endpoint scan |

## SMS configuration (`.env`)

```env
SMS_TO=+919354501373,+919876543210
TWILIO_ACCOUNT_SID=ACxxxx
TWILIO_AUTH_TOKEN=...
TWILIO_SMS_FROM=+17372508034
TWILIO_SMS_TEMPLATE=sms_internal_alerts
```

Multiple numbers: comma-separated in `SMS_TO`.

## Keyboard (when not headless)

| Key | Action |
|-----|--------|
| `q` | Quit |
| `s` | Snapshot |
