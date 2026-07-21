"""
CP Plus Camera Configuration
"""

CAMERA_IP = "122.175.45.21"
CAMERA_USER = "admin"
CAMERA_PASS = "Black$123"

# Common CP Plus / Dahua RTSP ports
RTSP_PORT = 554
HTTP_PORT = 80
HTTPS_PORT = 443
DAHUA_TCP_PORT = 37777   # Dahua proprietary SDK port

# RTSPS (RTSP over TLS) — confirmed working: 2560x1440 H.265 @ 25fps
# Port 554 uses TLS on this camera, so rtsps:// is required (not rtsp://)
RTSP_URLS = [
    f"rtsps://{CAMERA_USER}:{CAMERA_PASS}@{CAMERA_IP}:{RTSP_PORT}/video/live?channel=1&subtype=0",  # main HD
    f"rtsps://{CAMERA_USER}:{CAMERA_PASS}@{CAMERA_IP}:{RTSP_PORT}/video/live?channel=1&subtype=1",  # sub stream
    f"rtsps://{CAMERA_USER}:{CAMERA_PASS}@{CAMERA_IP}:{RTSP_PORT}/video/live?channel=2&subtype=0",  # channel 2
    f"rtsps://{CAMERA_USER}:{CAMERA_PASS}@{CAMERA_IP}:{RTSP_PORT}/cam/realmonitor?channel=1&subtype=0",
    f"rtsps://{CAMERA_USER}:{CAMERA_PASS}@{CAMERA_IP}:{RTSP_PORT}/cam/realmonitor?channel=1&subtype=1",
    f"rtsps://{CAMERA_USER}:{CAMERA_PASS}@{CAMERA_IP}:{RTSP_PORT}/",
]

# WebSocket endpoints common in CP Plus web portals
WS_ENDPOINTS = [
    f"ws://{CAMERA_IP}/websocket",
    f"ws://{CAMERA_IP}/live",
    f"ws://{CAMERA_IP}:80/websocket",
    f"ws://{CAMERA_IP}/RPC2_WebSocket",
    f"ws://{CAMERA_IP}/videostream",
]

# HTTP API endpoints (Dahua-based)
HTTP_SNAPSHOT = f"http://{CAMERA_IP}/cgi-bin/snapshot.cgi?channel=1"
HTTP_LOGIN = f"http://{CAMERA_IP}/RPC2_Login"
HTTP_STREAM = f"http://{CAMERA_IP}/cgi-bin/mjpg/video.cgi?channel=1&subtype=1"

# Violence detection model
VIOLENCE_WEIGHTS = "violence_yolov8n_cls-4/weights/best.pt"
VIOLENCE_CONF = 0.60          # alert when violence score >= this
VIOLENCE_EVERY_N = 3          # run inference every N frames
