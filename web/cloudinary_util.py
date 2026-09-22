"""Cloudinary deletes happen only on the web service (never on the Pi)."""

from __future__ import annotations

from config import CLOUDINARY_API_KEY, CLOUDINARY_API_SECRET, CLOUDINARY_CLOUD_NAME


def cloudinary_configured() -> bool:
    return bool(CLOUDINARY_CLOUD_NAME and CLOUDINARY_API_KEY and CLOUDINARY_API_SECRET)


def destroy_asset(public_id: str) -> bool:
    if not public_id or not cloudinary_configured():
        return False
    try:
        import cloudinary
        import cloudinary.uploader

        cloudinary.config(
            cloud_name=CLOUDINARY_CLOUD_NAME,
            api_key=CLOUDINARY_API_KEY,
            api_secret=CLOUDINARY_API_SECRET,
            secure=True,
        )
        cloudinary.uploader.destroy(public_id, invalidate=True)
        return True
    except Exception as e:
        print(f"  [web] Cloudinary delete failed: {e}")
        return False
