"""Shared RTSPS helpers — URL building, probe, and ffmpeg pipe."""

from __future__ import annotations

import shutil
import subprocess
import threading
from collections import deque

from config import CAMERA_IP, CAMERA_PASS, CAMERA_USER, RTSP_PORT

FFMPEG = shutil.which("ffmpeg") or "/opt/homebrew/bin/ffmpeg"
FFPROBE = shutil.which("ffprobe") or "/opt/homebrew/bin/ffprobe"

_tls_verify_cache: dict[str, bool] = {}


def _supports_tls_verify(binary: str) -> bool:
    """Debian ffmpeg rejects -tls_verify; Homebrew/macOS accepts it."""
    if binary not in _tls_verify_cache:
        try:
            r = subprocess.run(
                [binary, "-h", "full"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            _tls_verify_cache[binary] = "-tls_verify" in (r.stdout + r.stderr)
        except Exception:
            _tls_verify_cache[binary] = False
    return _tls_verify_cache[binary]


def ffmpeg_input_opts() -> list[str]:
    """ffmpeg input flags — keep minimal for broad ffmpeg version compatibility."""
    opts = ["-loglevel", "warning"]
    if _supports_tls_verify(FFMPEG):
        opts += ["-tls_verify", "0"]
    opts += ["-rtsp_transport", "tcp"]
    return opts


def ffprobe_input_opts() -> list[str]:
    opts = ["-v", "error"]
    if _supports_tls_verify(FFPROBE):
        opts += ["-tls_verify", "0"]
    return opts


def build_rtsp_url(channel: int = 1, subtype: int = 0) -> str:
    """Build RTSPS URL. Password is kept literal — this camera rejects %24 for $."""
    return (
        f"rtsps://{CAMERA_USER}:{CAMERA_PASS}@{CAMERA_IP}:{RTSP_PORT}"
        f"/video/live?channel={channel}&subtype={subtype}"
    )


def mask_url(url: str) -> str:
    if not CAMERA_PASS:
        return url
    return url.replace(CAMERA_PASS, "****")


def probe_stream(url: str, timeout: int = 20) -> dict | None:
    """Return video stream metadata, or None if unreachable."""
    masked = mask_url(url)
    print(f"  Probing: {masked}")
    r = subprocess.run(
        [
            FFPROBE,
            *ffprobe_input_opts(),
            "-select_streams", "v:0",
            "-show_entries", "stream=codec_name,width,height,r_frame_rate",
            "-of", "csv=p=0",
            url,
        ],
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    if r.returncode != 0:
        err = (r.stderr or r.stdout or "").strip()
        if err:
            print(f"  ffprobe error: {err[:400]}")
        return None

    lines = [ln.strip() for ln in r.stdout.strip().split("\n") if ln.strip()]
    if not lines:
        return None

    # Prefer the first line with valid video dimensions.
    for line in lines:
        parts = line.split(",")
        if len(parts) < 3:
            continue
        width = int(parts[1]) if parts[1].isdigit() else 0
        height = int(parts[2]) if parts[2].isdigit() else 0
        if width > 0 and height > 0:
            return {
                "codec": parts[0],
                "width": width,
                "height": height,
                "fps_str": parts[3] if len(parts) > 3 else "25/1",
            }

    print(f"  ffprobe returned no video dimensions: {lines!r}")
    return None


class _StderrTail:
    """Background reader that keeps the last N stderr lines from ffmpeg."""

    def __init__(self, proc: subprocess.Popen, max_lines: int = 20):
        self._lines: deque[str] = deque(maxlen=max_lines)
        self._proc = proc
        self._thread = threading.Thread(target=self._drain, daemon=True)
        self._thread.start()

    def _drain(self) -> None:
        if self._proc.stderr is None:
            return
        for raw in iter(self._proc.stderr.readline, b""):
            line = raw.decode(errors="replace").strip()
            if line:
                self._lines.append(line)

    def tail(self) -> str:
        return "\n".join(self._lines)


def open_ffmpeg_pipe(url: str, width: int, height: int) -> tuple[subprocess.Popen, _StderrTail]:
    cmd = [
        FFMPEG,
        *ffmpeg_input_opts(),
        "-i", url,
        "-an",
        "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2",
        "-f", "rawvideo",
        "-pix_fmt", "bgr24",
        "-",
    ]
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        bufsize=10 * width * height * 3,
    )
    return proc, _StderrTail(proc)


def log_stream_failure(proc: subprocess.Popen, stderr_tail: _StderrTail, got: int, expected: int) -> None:
    code = proc.poll()
    detail = stderr_tail.tail()
    print(
        f"  Stream read failed: got {got} bytes, expected {expected}"
        + (f", ffmpeg exit={code}" if code is not None else ", ffmpeg still running")
    )
    if detail:
        print(f"  ffmpeg stderr (last lines):\n{detail}")
