"""
Live Violence Detection on CP Plus Camera Feed.

Pulls RTSPS frames via ffmpeg, runs the YOLOv8 violence classifier,
overlays results, and saves alert clips/snapshots when violence is detected.

Usage:
    python3 violence_monitor.py                      # live window + alerts
    python3 violence_monitor.py --channel 1
    python3 violence_monitor.py --conf 0.7           # raise alert threshold
    python3 violence_monitor.py --every 5            # infer every 5th frame
    python3 violence_monitor.py --save-alerts        # save clips on violence
    python3 violence_monitor.py --headless --save-alerts
    python3 violence_monitor.py --weights path/to/best.pt
"""

from __future__ import annotations

import argparse
import collections
import csv
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np

from config import (
    ALERT_COOLDOWN_SEC,
    CAMERA_CHANNEL,
    CAMERA_IP,
    CAMERA_SUBTYPE,
    DEPLOY_HEADLESS,
    VIOLENCE_CONF,
    VIOLENCE_EVERY_N,
)
from notifier import AlertEvent, AlertNotifier, build_notifier_from_env
from stream_utils import (
    FFMPEG,
    build_rtsp_url,
    log_stream_failure,
    open_ffmpeg_pipe,
    probe_stream,
)
from violence_detector import DEFAULT_WEIGHTS, ViolenceDetector, ViolenceResult


def draw_overlay(
    frame: np.ndarray,
    result: ViolenceResult | None,
    fps: float,
    alert_active: bool,
) -> np.ndarray:
    disp = frame.copy()
    h, w = disp.shape[:2]

    # Status bar
    if result is None:
        color = (180, 180, 180)
        text = "Warming up..."
    elif result.is_violence:
        color = (0, 0, 255)
        text = f"VIOLENCE DETECTED  {result.confidence:.0%}"
    else:
        color = (0, 200, 0)
        text = f"SAFE  {result.label}  {result.confidence:.0%}"

    bar_h = max(48, h // 25)
    cv2.rectangle(disp, (0, 0), (w, bar_h), color, -1)
    cv2.putText(
        disp, text, (16, int(bar_h * 0.7)),
        cv2.FONT_HERSHEY_SIMPLEX, max(0.7, h / 900), (255, 255, 255), 2, cv2.LINE_AA,
    )

    # Meta
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cv2.putText(
        disp, f"{ts}  |  {fps:.1f} FPS  |  {CAMERA_IP}",
        (16, bar_h + 28), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1, cv2.LINE_AA,
    )

    if result is not None:
        y = bar_h + 55
        for name, score in result.scores.items():
            cv2.putText(
                disp, f"{name}: {score:.1%}",
                (16, y), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (220, 220, 220), 1, cv2.LINE_AA,
            )
            y += 22

    if alert_active:
        cv2.rectangle(disp, (8, 8), (w - 8, h - 8), (0, 0, 255), 6)
        cv2.putText(
            disp, "ALERT", (w - 160, bar_h + 40),
            cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 255), 3, cv2.LINE_AA,
        )

    return disp


class AlertManager:
    """Saves snapshots + short clips when violence is confirmed."""

    def __init__(
        self,
        out_dir: Path,
        cooldown_sec: float = 10.0,
        buffer_size: int = 75,
        notifier: AlertNotifier | None = None,
        channel: int = 1,
    ):
        self.out_dir = out_dir
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self.cooldown_sec = cooldown_sec
        self.buffer: collections.deque = collections.deque(maxlen=buffer_size)
        self.last_alert_time = 0.0
        self.notifier = notifier
        self.channel = channel
        self.log_path = self.out_dir / "alerts.csv"
        if not self.log_path.exists():
            with open(self.log_path, "w", newline="") as f:
                csv.writer(f).writerow(
                    ["timestamp", "confidence", "label", "snapshot", "clip"]
                )

    def push(self, frame: np.ndarray):
        self.buffer.append(frame.copy())

    def maybe_alert(self, result: ViolenceResult) -> Path | None:
        now = time.time()
        if not result.is_violence:
            return None
        if now - self.last_alert_time < self.cooldown_sec:
            return None

        self.last_alert_time = now
        detected_at = datetime.now().astimezone()
        stamp = detected_at.strftime("%Y%m%d_%H%M%S")
        snap_path = self.out_dir / f"alert_{stamp}.jpg"
        clip_path = self.out_dir / f"alert_{stamp}.mp4"

        # Snapshot = latest frame
        if self.buffer:
            cv2.imwrite(str(snap_path), self.buffer[-1])

        # Clip = buffered frames
        if len(self.buffer) >= 5:
            h, w = self.buffer[0].shape[:2]
            writer = cv2.VideoWriter(
                str(clip_path),
                cv2.VideoWriter_fourcc(*"mp4v"),
                12.0,
                (w, h),
            )
            for f in self.buffer:
                writer.write(f)
            writer.release()
        else:
            clip_path = Path("")

        with open(self.log_path, "a", newline="") as f:
            csv.writer(f).writerow([
                detected_at.isoformat(timespec="seconds"),
                f"{result.confidence:.4f}",
                result.label,
                snap_path.name,
                clip_path.name if clip_path else "",
            ])

        print(f"\n  ALERT saved → {snap_path.name}"
              + (f" + {clip_path.name}" if clip_path else ""))

        # Supabase + WhatsApp
        if self.notifier:
            self.notifier.notify(AlertEvent(
                detected_at=detected_at,
                confidence=result.confidence,
                label=result.label,
                camera_ip=CAMERA_IP,
                channel=self.channel,
                snapshot_path=snap_path.name,
                clip_path=clip_path.name if clip_path else None,
            ))

        return snap_path


def run_monitor(
    url: str,
    info: dict,
    detector: ViolenceDetector,
    every_n: int = 3,
    save_alerts: bool = True,
    headless: bool = False,
    display_scale: float = 0.5,
    notifier: AlertNotifier | None = None,
    channel: int = 1,
    cooldown_sec: float = ALERT_COOLDOWN_SEC,
):
    w, h = info["width"], info["height"]
    if w == 0 or h == 0:
        print("ERROR: Could not determine stream resolution from ffprobe.")
        sys.exit(1)

    frame_size = w * h * 3
    alert_mgr = (
        AlertManager(
            Path("alerts"),
            notifier=notifier,
            channel=channel,
            cooldown_sec=cooldown_sec,
        )
        if save_alerts else None
    )

    latest: ViolenceResult | None = None
    frame_count = 0
    infer_count = 0
    start = time.time()
    consecutive_hits = 0
    alert_active = False

    print(f"\nStream: {w}x{h} {info['codec'].upper()} @ {info['fps_str']}")
    print(f"Inference every {every_n} frame(s)  |  threshold={detector.conf_threshold:.0%}")
    print("Press 'q' to quit, 's' for snapshot\n")

    reconnects = 0
    while True:
        proc, stderr_tail = open_ffmpeg_pipe(url, w, h)
        try:
            while True:
                raw = proc.stdout.read(frame_size)
                if len(raw) != frame_size:
                    reconnects += 1
                    log_stream_failure(proc, stderr_tail, len(raw), frame_size)
                    if reconnects == 1 or reconnects % 10 == 0:
                        print(f"Stream interrupted — reconnecting in 2s... (attempt {reconnects})")
                    else:
                        print("Stream interrupted — reconnecting in 2s...")
                    time.sleep(2)
                    break

                frame = np.frombuffer(raw, dtype=np.uint8).reshape((h, w, 3))
                frame_count += 1

                if alert_mgr:
                    # Store downscaled frames in buffer to keep memory reasonable
                    small = cv2.resize(frame, (min(960, w), int(min(960, w) * h / w)))
                    alert_mgr.push(small)

                # Run inference on a stride
                if frame_count % every_n == 0:
                    latest = detector.predict(frame)
                    infer_count += 1

                    if latest.is_violence:
                        consecutive_hits += 1
                    else:
                        consecutive_hits = max(0, consecutive_hits - 1)

                    # Require 2 consecutive hits to reduce false alarms
                    alert_active = consecutive_hits >= 2
                    if alert_active and alert_mgr:
                        alert_mgr.maybe_alert(latest)

                elapsed = time.time() - start
                fps = frame_count / elapsed if elapsed > 0 else 0

                if not headless:
                    disp = draw_overlay(frame, latest, fps, alert_active)
                    if display_scale != 1.0:
                        disp = cv2.resize(
                            disp, None, fx=display_scale, fy=display_scale,
                            interpolation=cv2.INTER_AREA,
                        )
                    cv2.imshow("Violence Monitor — CP Plus", disp)
                    key = cv2.waitKey(1) & 0xFF
                    if key == ord("q"):
                        raise KeyboardInterrupt
                    elif key == ord("s"):
                        fn = f"snapshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
                        cv2.imwrite(fn, frame)
                        print(f"Snapshot: {fn}")
                elif frame_count % 25 == 0:
                    status = latest or "warming up"
                    print(f"  frames={frame_count}  infer={infer_count}  fps={fps:.1f}  {status}")

        except KeyboardInterrupt:
            break
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=3)
            except Exception:
                proc.kill()

    if not headless:
        cv2.destroyAllWindows()

    print(f"\nDone. Frames={frame_count}  Inferences={infer_count}")
    if alert_mgr:
        print(f"Alerts folder: {alert_mgr.out_dir.resolve()}")


def main():
    parser = argparse.ArgumentParser(description="Live Violence Detection on CP Plus feed")
    parser.add_argument("--channel", type=int, default=CAMERA_CHANNEL)
    parser.add_argument("--subtype", type=int, default=CAMERA_SUBTYPE, choices=[0, 1],
                        help="0=main HD (slower), 1=sub-stream (recommended for ML)")
    parser.add_argument("--weights", default=str(DEFAULT_WEIGHTS))
    parser.add_argument("--conf", type=float, default=VIOLENCE_CONF,
                        help="Violence confidence threshold")
    parser.add_argument("--every", type=int, default=VIOLENCE_EVERY_N,
                        help="Run inference every N frames")
    parser.add_argument("--cooldown", type=float, default=ALERT_COOLDOWN_SEC,
                        help="Seconds between SMS alerts")
    parser.add_argument("--device", default=None, help="cpu / mps / 0")
    parser.add_argument("--save-alerts", action="store_true", default=True)
    parser.add_argument("--no-alerts", action="store_true")
    parser.add_argument("--headless", action="store_true",
                        help="No display window (default from DEPLOY_HEADLESS in .env)")
    parser.add_argument("--scale", type=float, default=0.5,
                        help="Display scale factor (default 0.5)")
    parser.add_argument("--no-sms", action="store_true",
                        help="Skip SMS notifications")
    parser.add_argument("--test-sms", action="store_true",
                        help="Send test SMS + log to Supabase, then exit")
    parser.add_argument("--test-log", action="store_true",
                        help="Log a test detection to Supabase only (no SMS)")
    parser.add_argument("--probe-only", action="store_true",
                        help="Test camera connection and print stream info, then exit")
    parser.add_argument("--no-whatsapp", action="store_true",
                        help="Deprecated alias for --no-sms")
    parser.add_argument("--test-whatsapp", action="store_true",
                        help="Deprecated alias for --test-sms")
    args = parser.parse_args()

    if args.no_whatsapp:
        args.no_sms = True
    if args.test_whatsapp:
        args.test_sms = True

    headless = args.headless or DEPLOY_HEADLESS

    print("=" * 60)
    print("  Violence Detection — Live Monitor")
    print(f"  Camera: {CAMERA_IP}  Channel: {args.channel}")
    print(f"  Weights: {args.weights}")
    print(f"  Mode: {'headless (deploy)' if headless else 'display'}")
    print("=" * 60)

    notifier = None if args.no_alerts else build_notifier_from_env()
    if notifier and args.no_sms:
        notifier.sms_enabled = False
        notifier._twilio = None

    if args.test_log or args.test_sms:
        if notifier is None or not notifier.enabled:
            print("ERROR: Set SUPABASE_LOGGING=true + Supabase keys in .env")
            print("       (and Twilio keys for --test-sms)")
            sys.exit(1)
        if args.test_log:
            notifier.sms_enabled = False
            notifier._twilio = None
        result = notifier.notify(AlertEvent(
            detected_at=datetime.now().astimezone(),
            confidence=0.99,
            label="violence",
            camera_ip=CAMERA_IP,
            channel=args.channel,
            snapshot_path="test",
        ))
        print("Test result:", result)
        sys.exit(0 if result.get("ok") else 1)

    if not Path(FFMPEG).exists() and not shutil.which("ffmpeg"):
        print("ERROR: ffmpeg not found. Install with: brew install ffmpeg")
        sys.exit(1)

    print("\nLoading model...")
    detector = ViolenceDetector(
        weights=args.weights,
        conf_threshold=args.conf,
        device=args.device,
    )
    print(f"  Classes: {detector.names}")
    print(f"  Threshold: {detector.conf_threshold:.0%}")
    if notifier and notifier.enabled:
        if notifier._supabase:
            print("  Supabase: logging enabled")
        if notifier.sms_enabled:
            print(f"  SMS: enabled → {', '.join(notifier.recipients)}")
        elif not notifier._supabase:
            print("  Alerts: disabled")
    else:
        print("  Alerts: disabled (set SUPABASE_LOGGING or SMS in .env)")

    url = build_rtsp_url(args.channel, args.subtype)
    print("\nConnecting to camera...")
    info = probe_stream(url)
    if not info:
        print("ERROR: Could not open stream. Check network / credentials.")
        print("  Tips: ensure port 554 is reachable from Render; use CAMERA_SUBTYPE=1;")
        print("  verify CAMERA_PASS in Render (special chars like $ must match exactly).")
        sys.exit(1)
    print(f"  Connected: {info['width']}x{info['height']} {info['codec']}")

    if args.probe_only:
        proc, stderr_tail = open_ffmpeg_pipe(url, info["width"], info["height"])
        frame_size = info["width"] * info["height"] * 3
        raw = proc.stdout.read(frame_size)
        proc.terminate()
        if len(raw) == frame_size:
            print("  First frame: OK")
            sys.exit(0)
        log_stream_failure(proc, stderr_tail, len(raw), frame_size)
        print("ERROR: Connected but could not read a full video frame.")
        sys.exit(1)

    run_monitor(
        url=url,
        info=info,
        detector=detector,
        every_n=max(1, args.every),
        save_alerts=not args.no_alerts,
        headless=headless,
        display_scale=args.scale,
        notifier=notifier,
        channel=args.channel,
        cooldown_sec=args.cooldown,
    )


if __name__ == "__main__":
    main()
