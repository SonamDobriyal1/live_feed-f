"""
Application configuration — loaded from .env for deployment.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

# Camera
CAMERA_IP = os.getenv("CAMERA_IP", "122.175.45.21")
CAMERA_USER = os.getenv("CAMERA_USER", "admin")
CAMERA_PASS = os.getenv("CAMERA_PASS", "")
RTSP_PORT = int(os.getenv("RTSP_PORT", "554"))
CAMERA_CHANNEL = int(os.getenv("CAMERA_CHANNEL", "1"))
CAMERA_SUBTYPE = int(os.getenv("CAMERA_SUBTYPE", "1"))

HTTP_PORT = 80
HTTPS_PORT = 443
DAHUA_TCP_PORT = 37777

# RTSPS URLs (rtsps:// required for this camera)
RTSP_URLS = [
    f"rtsps://{CAMERA_USER}:{CAMERA_PASS}@{CAMERA_IP}:{RTSP_PORT}/video/live?channel={CAMERA_CHANNEL}&subtype={CAMERA_SUBTYPE}",
    f"rtsps://{CAMERA_USER}:{CAMERA_PASS}@{CAMERA_IP}:{RTSP_PORT}/video/live?channel={CAMERA_CHANNEL}&subtype={1 - CAMERA_SUBTYPE}",
    f"rtsps://{CAMERA_USER}:{CAMERA_PASS}@{CAMERA_IP}:{RTSP_PORT}/cam/realmonitor?channel={CAMERA_CHANNEL}&subtype=0",
    f"rtsps://{CAMERA_USER}:{CAMERA_PASS}@{CAMERA_IP}:{RTSP_PORT}/",
]

WS_ENDPOINTS = [
    f"ws://{CAMERA_IP}/websocket",
    f"ws://{CAMERA_IP}/live",
    f"ws://{CAMERA_IP}:80/websocket",
    f"ws://{CAMERA_IP}/RPC2_WebSocket",
    f"ws://{CAMERA_IP}/videostream",
]

HTTP_SNAPSHOT = f"http://{CAMERA_IP}/cgi-bin/snapshot.cgi?channel=1"
HTTP_LOGIN = f"http://{CAMERA_IP}/RPC2_Login"
HTTP_STREAM = f"http://{CAMERA_IP}/cgi-bin/mjpg/video.cgi?channel=1&subtype=1"

# Violence model
VIOLENCE_WEIGHTS = os.getenv(
    "VIOLENCE_WEIGHTS",
    "violence_yolov8n_cls-4/weights/best.pt",
)
VIOLENCE_CONF = float(os.getenv("VIOLENCE_CONF", "0.60"))
VIOLENCE_EVERY_N = int(os.getenv("VIOLENCE_EVERY_N", "3"))
ALERT_COOLDOWN_SEC = float(os.getenv("ALERT_COOLDOWN_SEC", "10"))

# Deployment
DEPLOY_HEADLESS = os.getenv("DEPLOY_HEADLESS", "true").lower() in ("1", "true", "yes")

# SMS / Twilio
SMS_ENABLED = os.getenv("SMS_ENABLED", "true").lower() in ("1", "true", "yes")
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "")
TWILIO_SMS_FROM = os.getenv("TWILIO_SMS_FROM", "")
TWILIO_SMS_TEMPLATE = os.getenv("TWILIO_SMS_TEMPLATE", "sms_internal_alerts")
TWILIO_SMS_USE_TEMPLATE = os.getenv("TWILIO_SMS_USE_TEMPLATE", "true").lower() in (
    "1", "true", "yes",
)
# Optional: Content Template SID from Twilio Content Builder (HX...)
# Only use with TWILIO_SMS_MODE=content. For India trial sms_internal_alerts,
# leave this empty and use TWILIO_SMS_MODE=template instead.
TWILIO_CONTENT_SID = os.getenv("TWILIO_CONTENT_SID", "")
# template = Body=sms_internal_alerts (India trial — recommended)
# content  = ContentSid API only
# auto     = try ContentSid, fall back to template name
TWILIO_SMS_MODE = os.getenv("TWILIO_SMS_MODE", "auto").lower()
SMS_TO = os.getenv("SMS_TO", "")

# Optional Supabase logging
SUPABASE_LOGGING = os.getenv("SUPABASE_LOGGING", "false").lower() in ("1", "true", "yes")
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "")


def parse_sms_recipients(raw: str | None = None) -> list[str]:
    """Parse comma/semicolon/newline-separated phone numbers into E.164 list."""
    text = raw if raw is not None else SMS_TO
    numbers: list[str] = []
    for part in text.replace(";", ",").replace("\n", ",").split(","):
        n = part.strip()
        if not n:
            continue
        if not n.startswith("+"):
            n = f"+{n}"
        numbers.append(n)
    return numbers
