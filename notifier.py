"""
Supabase + WhatsApp notifier for violence alerts.

Flow:
  1. Insert alert row into Supabase `violence_alerts`
  2. Invoke Edge Function `send-violence-whatsapp` (Twilio WhatsApp)

Env vars (put in .env next to this file):
  SUPABASE_URL=https://xxxx.supabase.co
  SUPABASE_ANON_KEY=eyJ...
  SUPABASE_SERVICE_ROLE_KEY=eyJ...   # optional, preferred for inserts
  WHATSAPP_ENABLED=true
  # Edge function is used by default; Twilio secrets live in Supabase
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")


@dataclass
class AlertEvent:
    detected_at: datetime
    confidence: float
    label: str
    camera_ip: str
    channel: int = 1
    snapshot_path: str | None = None
    clip_path: str | None = None

    def message_text(self) -> str:
        when = self.detected_at.astimezone().strftime("%d %b %Y, %I:%M:%S %p")
        return (
            "⚠️ Possible Violence Detected\n\n"
            f"Time: {when}\n"
            f"Confidence: {self.confidence:.1%}\n"
            f"Camera: {self.camera_ip} (ch {self.channel})\n"
            f"Label: {self.label}\n\n"
            "Please verify on the live feed."
        )

    def to_row(self) -> dict[str, Any]:
        return {
            "detected_at": self.detected_at.astimezone(timezone.utc).isoformat(),
            "camera_ip": self.camera_ip,
            "channel": self.channel,
            "confidence": float(self.confidence),
            "label": self.label,
            "snapshot_path": self.snapshot_path,
            "clip_path": self.clip_path,
            "message": self.message_text(),
            "whatsapp_status": "pending",
        }


class SupabaseWhatsAppNotifier:
    """Inserts alerts into Supabase and triggers WhatsApp via Edge Function."""

    def __init__(
        self,
        supabase_url: str | None = None,
        supabase_key: str | None = None,
        enabled: bool | None = None,
        function_name: str = "send-violence-whatsapp",
    ):
        self.url = (supabase_url or os.getenv("SUPABASE_URL", "")).rstrip("/")
        self.key = (
            supabase_key
            or os.getenv("SUPABASE_SERVICE_ROLE_KEY")
            or os.getenv("SUPABASE_ANON_KEY")
            or ""
        )
        env_flag = os.getenv("WHATSAPP_ENABLED", "true").lower()
        self.enabled = enabled if enabled is not None else env_flag in ("1", "true", "yes")
        self.function_name = function_name
        self._client = None

        if not self.url or not self.key:
            print(
                "  [notifier] SUPABASE_URL / key not set — "
                "alerts will stay local only (no WhatsApp)."
            )
            self.enabled = False
            return

        try:
            from supabase import create_client
            self._client = create_client(self.url, self.key)
            print("  [notifier] Supabase connected")
        except Exception as e:
            print(f"  [notifier] Failed to init Supabase client: {e}")
            self.enabled = False

    def notify(self, event: AlertEvent) -> dict[str, Any]:
        """
        Save alert to Supabase and send WhatsApp.
        Returns a small status dict.
        """
        if not self.enabled or self._client is None:
            return {"ok": False, "reason": "disabled"}

        row = event.to_row()
        inserted: dict[str, Any] | None = None

        try:
            resp = self._client.table("violence_alerts").insert(row).execute()
            inserted = (resp.data or [None])[0]
            print(f"  [notifier] Saved to Supabase id={inserted.get('id') if inserted else '?'}")
        except Exception as e:
            print(f"  [notifier] Supabase insert failed: {e}")
            return {"ok": False, "reason": f"insert_failed: {e}"}

        # Invoke Edge Function (Twilio WhatsApp)
        payload = inserted or row
        try:
            fn = self._client.functions.invoke(
                self.function_name,
                invoke_options={"body": payload},
            )
            # supabase-py may return bytes/str/dict depending on version
            print(f"  [notifier] WhatsApp function response: {fn}")
            return {"ok": True, "alert": inserted, "whatsapp": fn}
        except Exception as e:
            print(f"  [notifier] WhatsApp Edge Function failed: {e}")
            # Mark failed on the row if we have an id
            try:
                if inserted and inserted.get("id"):
                    self._client.table("violence_alerts").update({
                        "whatsapp_status": "failed",
                        "whatsapp_error": str(e),
                    }).eq("id", inserted["id"]).execute()
            except Exception:
                pass
            return {"ok": False, "reason": f"whatsapp_failed: {e}", "alert": inserted}


def build_notifier_from_env() -> SupabaseWhatsAppNotifier | None:
    """Return a notifier if env is configured; otherwise None."""
    if not os.getenv("SUPABASE_URL"):
        return None
    return SupabaseWhatsAppNotifier()
