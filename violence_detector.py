"""
YOLOv8 violence classifier wrapper.

Model: violence_yolov8n_cls-4/weights/best.pt
Classes: 0 = non_violence, 1 = violence
Input size: 224x224
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
from ultralytics import YOLO

DEFAULT_WEIGHTS = Path(__file__).parent / "violence_yolov8n_cls-4" / "weights" / "best.pt"


@dataclass
class ViolenceResult:
    label: str
    confidence: float
    is_violence: bool
    scores: dict[str, float]

    def __str__(self) -> str:
        return f"{self.label} ({self.confidence:.1%})"


class ViolenceDetector:
    def __init__(
        self,
        weights: str | Path = DEFAULT_WEIGHTS,
        conf_threshold: float = 0.60,
        device: str | None = None,
    ):
        weights = Path(weights)
        if not weights.exists():
            raise FileNotFoundError(f"Model weights not found: {weights}")

        self.model = YOLO(str(weights))
        self.conf_threshold = conf_threshold
        self.device = device
        self.names = dict(self.model.names)  # {0: 'non_violence', 1: 'violence'}
        self.violence_idx = next(
            (i for i, n in self.names.items() if "violence" in n.lower() and "non" not in n.lower()),
            1,
        )

    def predict(self, frame_bgr: np.ndarray) -> ViolenceResult:
        """Classify a single BGR frame. Returns ViolenceResult."""
        kwargs = {"verbose": False, "imgsz": 224}
        if self.device:
            kwargs["device"] = self.device

        results = self.model.predict(frame_bgr, **kwargs)
        probs = results[0].probs

        top1 = int(probs.top1)
        top1_conf = float(probs.top1conf)
        raw = probs.data.cpu().numpy()
        scores = {self.names[i]: float(raw[i]) for i in range(len(self.names))}

        violence_conf = scores.get(self.names[self.violence_idx], 0.0)
        is_violence = violence_conf >= self.conf_threshold
        label = self.names[top1]

        # Prefer violence label when above threshold even if not top1
        if is_violence:
            label = self.names[self.violence_idx]
            top1_conf = violence_conf

        return ViolenceResult(
            label=label,
            confidence=top1_conf,
            is_violence=is_violence,
            scores=scores,
        )
