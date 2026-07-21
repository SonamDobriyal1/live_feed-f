# CP Plus Camera Live Feed

Live video feed client for CP Plus / Dahua IP cameras.  
Supports **RTSP**, **MJPEG over HTTP**, and **WebSocket** streaming.

## Quick Start

```bash
# Install dependencies
pip3 install -r requirements.txt

# Step 1: Check what's available on the camera
python3 probe.py

# Step 2: Auto-detect the best stream method and display
python3 live_feed.py
```

## Scripts

| Script | Purpose |
|--------|---------|
| `probe.py` | Scan open ports, detect firmware, find working endpoints |
| `live_feed.py` | Main entry point — auto-detects the best method |
| `rtsp_viewer.py` | RTSP stream viewer (best quality) |
| `mjpeg_viewer.py` | MJPEG HTTP stream viewer (simplest) |
| `websocket_client.py` | WebSocket stream viewer (web-portal protocol) |

## Usage Examples

```bash
# Auto mode (recommended)
python3 live_feed.py

# Specific channel
python3 live_feed.py --channel 2

# Force a specific method
python3 live_feed.py --method rtsp
python3 live_feed.py --method mjpeg
python3 live_feed.py --method websocket

# Save to file
python3 live_feed.py --save recording.mp4

# Capture a single snapshot PNG
python3 live_feed.py --snapshot

# Check which camera channels are active
python3 live_feed.py --list-channels

# RTSP sub-stream (lower resolution, less bandwidth)
python3 live_feed.py --method rtsp --subtype 1
```

## Keyboard Controls (while viewing)

| Key | Action |
|-----|--------|
| `q` | Quit |
| `s` | Save snapshot |

## Camera Details

- **IP**: `223.230.3.31`
- **Username**: `admin`
- **RTSP Port**: `554`

Edit `config.py` to change camera credentials or IP.

## Troubleshooting

**Can't connect?**
- Ensure you are on the **same network** as the camera (or connected via VPN)
- Run `python3 probe.py` to check which ports are reachable
- The camera at `223.230.3.31` is a private/LAN IP — you must be on that LAN

**Wrong RTSP URL format?**
- Open the camera's web portal in Chrome
- Press `F12` → **Network** tab → filter by `ws` (WebSocket) or `rtsp`
- The exact URL used by the browser will appear there

**WebSocket method not finding frames?**
- Open the portal in Chrome DevTools → Network → WS tab
- Find the WebSocket connection URL and pass it directly:
  ```bash
  python3 websocket_client.py --ws ws://223.230.3.31/your-ws-path
  ```

## How CP Plus WebSocket Streaming Works

CP Plus cameras (which use Dahua firmware) implement WebSocket streaming via:

1. **Dahua RPC2 WebSocket** (`/RPC2_WebSocket`) — JSON-RPC handshake followed by binary H.264/JPEG frames
2. **JSMPEG WebSocket** — raw MJPEG frames pushed over WebSocket
3. **Generic binary WebSocket** — JPEG frames embedded in binary messages

The `websocket_client.py` tries all three patterns automatically.
