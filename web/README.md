# Web dashboard

Flask app for daycare staff. Independent of the Pi ML process.

- Login: **camera IP** + **camera password**
- Each daycare only sees its own detections
- **Save** — keep after midnight
- **Delete** — remove from the portal **and** Cloudinary (logic is only here)
- Unsaved items are auto-deleted at midnight (`DAYCARE_TZ`)

```bash
pip3 install -r requirements.txt
cp .env.example .env
python3 seed.py --ip CAMERA_IP --password 'CAMERA_PASSWORD' --name 'Daycare Name'
python3 app.py
```

Pi devices POST to `POST /api/detections` with header `X-Ingest-Key`.

## Production (Render / VPS)

See **[WEB_DEPLOY.md](../WEB_DEPLOY.md)**. Local `PORTAL_URL=http://127.0.0.1:8080` will not work from a Pi at another site.
