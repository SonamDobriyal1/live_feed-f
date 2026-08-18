# Deploy on Render (headless — no live feed)

Run the violence detection model 24/7 on Render. **No video window** — only ML inference on your CCTV stream + SMS alerts.

## Requirements

- Camera must be **reachable from the public internet** (Render runs in the cloud)
  - Your camera IP `122.175.45.21` with port **554** open worked before
- Model weights committed or present in repo: `violence_yolov8n_cls-4/weights/best.pt`
- Twilio account for SMS
- **Render Starter Worker** plan (recommended) — free tier is not suitable for 24/7 monitoring

## Option A — Blueprint (easiest)

1. Push this repo to GitHub
2. Go to [Render Dashboard](https://dashboard.render.com) → **New** → **Blueprint**
3. Connect the repo — Render reads `render.yaml`
4. Set secret env vars when prompted (camera password, Twilio, SMS numbers)
5. Click **Apply** — worker starts automatically

## Option B — Manual worker

1. **New** → **Background Worker**
2. Connect GitHub repo
3. Settings:
   - **Language:** Docker
   - **Dockerfile path:** `./Dockerfile`
   - **Plan:** Starter (or higher)
   - **Region:** Singapore (closest to India cameras)
4. Add **Environment Variables** (see table below)
5. **Create Background Worker**

## Environment variables (Render Dashboard)

Set these under your worker → **Environment**:

| Variable | Example | Secret? |
|----------|---------|---------|
| `CAMERA_IP` | `122.175.45.21` | |
| `CAMERA_USER` | `admin` | |
| `CAMERA_PASS` | your password | Yes |
| `RTSP_PORT` | `554` | |
| `CAMERA_CHANNEL` | `1` | |
| `CAMERA_SUBTYPE` | `1` | sub-stream, less CPU |
| `DEPLOY_HEADLESS` | `true` | always true on Render |
| `SMS_ENABLED` | `true` | |
| `SMS_TO` | `+919354501373,+91...` | comma-separated |
| `TWILIO_ACCOUNT_SID` | `ACxxxx...` | Yes |
| `TWILIO_AUTH_TOKEN` | your token | Yes |
| `TWILIO_SMS_FROM` | `+17372508034` | |
| `TWILIO_SMS_TEMPLATE` | `sms_internal_alerts` | India trial |
| `TWILIO_SMS_USE_TEMPLATE` | `true` | |
| `VIOLENCE_CONF` | `0.60` | |
| `VIOLENCE_EVERY_N` | `3` | higher = less CPU |
| `ALERT_COOLDOWN_SEC` | `10` | |

No `.env` file on Render — all values go in the Dashboard.

## Verify deployment

1. Open worker → **Logs**
2. Look for:
   ```
   Violence Detection — Live Monitor
   Mode: headless (deploy)
   [notifier] Twilio ready → N recipient(s)
   Connected: 1280x720 hevc
   ```
3. On detection you should see `ALERT saved` and `SMS sent → +91...`

## Test SMS before going live

Run locally first:
```bash
python3 violence_monitor.py --test-sms
```

## Important notes

- **No live feed on Render** — the worker only runs inference + SMS. View video locally with `python3 rtsp_viewer.py` if needed.
- **CPU/RAM:** YOLOv8 + ffmpeg is heavy. Use `CAMERA_SUBTYPE=1` and `VIOLENCE_EVERY_N=5` if the worker OOMs or is slow.
- **Alerts folder** is ephemeral on Render (lost on restart). Enable `SUPABASE_LOGGING=true` to persist alert records.
- **Camera offline:** worker reconnects automatically; check logs if stream fails repeatedly.

## Troubleshooting

| Log message | Fix |
|-------------|-----|
| `Could not open stream` | Camera IP/port not reachable from Render; check firewall |
| `SMS disabled` | Set `SMS_TO` and Twilio vars in Dashboard |
| `Invalid template name` | Set `TWILIO_SMS_TEMPLATE=sms_internal_alerts` |
| Worker keeps restarting | Upgrade plan or reduce `VIOLENCE_EVERY_N`, use sub-stream |
