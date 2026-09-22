"""Pi-only: upload snapshots to Cloudinary and POST metadata to the web dashboard."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from urllib.parse import urljoin

import cv2
import numpy as np

from config import (
    CAMERA_IP,
    CLOUDINARY_API_KEY,
    CLOUDINARY_API_SECRET,
    CLOUDINARY_CLOUD_NAME,
    CLOUDINARY_FOLDER,
    DAYCARE_NAME,
    PORTAL_INGEST_KEY,
    PORTAL_URL,
)


def _folder_slug(camera_ip: str) -> str:
    return camera_ip.replace(".", "-").replace(":", "-")


def cloudinary_configured() -> bool:
    return bool(CLOUDINARY_CLOUD_NAME and CLOUDINARY_API_KEY and CLOUDINARY_API_SECRET)


def upload_snapshot(
    frame_bgr: np.ndarray,
    detected_at: datetime,
    camera_ip: str = CAMERA_IP,
) -> dict[str, str]:
    if not cloudinary_configured():
        raise RuntimeError("Cloudinary credentials missing")

    import cloudinary
    import cloudinary.uploader

    cloudinary.config(
        cloud_name=CLOUDINARY_CLOUD_NAME,
        api_key=CLOUDINARY_API_KEY,
        api_secret=CLOUDINARY_API_SECRET,
        secure=True,
    )

    ok, buf = cv2.imencode(".jpg", frame_bgr, [int(cv2.IMWRITE_JPEG_QUALITY), 70])
    if not ok:
        raise RuntimeError("Failed to encode JPEG snapshot")

    stamp = detected_at.strftime("%Y%m%d_%H%M%S")
    folder = f"{CLOUDINARY_FOLDER}/{_folder_slug(camera_ip)}"
    public_id = f"{folder}/alert_{stamp}"

    result = cloudinary.uploader.upload(
        buf.tobytes(),
        public_id=public_id,
        resource_type="image",
        overwrite=True,
        invalidate=True,
    )
    return {
        "public_id": result.get("public_id", public_id),
        "url": result.get("secure_url") or result.get("url") or "",
    }


def post_detection_to_web(payload: dict[str, Any], retries: int = 4) -> dict[str, Any] | None:
    if not PORTAL_URL or not PORTAL_INGEST_KEY:
        print("  [web] PORTAL_URL or PORTAL_INGEST_KEY missing — skip dashboard ingest")
        return None

    import json
    import time
    import urllib.error
    import urllib.request

    body = json.dumps(payload).encode("utf-8")
    url = urljoin(PORTAL_URL + "/", "api/detections")
    last_err = None
    for attempt in range(1, retries + 1):
        req = urllib.request.Request(
            url,
            data=body,
            headers={
                "Content-Type": "application/json",
                "X-Ingest-Key": PORTAL_INGEST_KEY,
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                raw = resp.read().decode("utf-8")
                return json.loads(raw) if raw else {"ok": True}
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", errors="replace")[:300]
            print(f"  [web] ingest failed HTTP {e.code}: {detail}")
            return None
        except Exception as e:
            last_err = e
            wait = min(2 ** attempt, 8)
            print(f"  [web] ingest attempt {attempt}/{retries} failed: {e}")
            if attempt < retries:
                print(f"  [web] retrying in {wait}s — is `python3 app.py` running in web/?")
                time.sleep(wait)
    print(f"  [web] ingest gave up: {last_err}")
    return None


def publish_detection(
    frame_bgr: np.ndarray,
    detected_at: datetime,
    confidence: float,
    label: str,
    channel: int,
) -> dict[str, Any]:
    """Upload snapshot then notify the web service. Safe on a background thread."""
    out: dict[str, Any] = {"cloudinary": None, "web": None}
    try:
        uploaded = upload_snapshot(frame_bgr, detected_at)
        out["cloudinary"] = uploaded
        print(f"  [cloud] Cloudinary → {uploaded['url']}")
    except Exception as e:
        print(f"  [cloud] upload failed: {e}")
        uploaded = {"public_id": "", "url": ""}

    web = post_detection_to_web({
        "camera_ip": CAMERA_IP,
        "daycare_name": DAYCARE_NAME or CAMERA_IP,
        "detected_at": detected_at.isoformat(),
        "confidence": float(confidence),
        "label": label,
        "channel": channel,
        "snapshot_url": uploaded.get("url", ""),
        "cloudinary_public_id": uploaded.get("public_id", ""),
    })
    out["web"] = web
    if web:
        print(f"  [web] logged detection id={web.get('id', '?')}")
    return out
