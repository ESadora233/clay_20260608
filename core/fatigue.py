"""疲劳值 OCR 识别（左上角 120/100 格式）。"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

import cv2
import numpy as np

logger = logging.getLogger(__name__)

_FATIGUE_PATTERN = re.compile(r"(\d+)\s*/\s*(\d+)")
_OCR = None


@dataclass
class FatigueConfig:
    enabled: bool = True
    stop_at: int = 0
    region: tuple[float, float, float, float] = (0.08, 0.05, 0.08, 0.10)


@dataclass
class FatigueResult:
    current: int | None
    max_value: int | None
    raw_text: str = ""

    @property
    def ok(self) -> bool:
        return self.current is not None

    @property
    def should_stop(self) -> bool:
        return self.ok and self.current <= 0


def _get_ocr():
    global _OCR
    if _OCR is None:
        from rapidocr_onnxruntime import RapidOCR

        _OCR = RapidOCR()
    return _OCR


class FatigueReader:
    def __init__(self, config: FatigueConfig, debug_dir: str | None = None) -> None:
        self.config = config
        self.debug_dir = debug_dir

    def read(self, screen: np.ndarray, save_debug: bool = False) -> FatigueResult:
        if not self.config.enabled:
            return FatigueResult(current=None, max_value=None)

        crop = self.crop_region(screen)
        if save_debug and self.debug_dir:
            path = f"{self.debug_dir}/fatigue_crop.png"
            cv2.imwrite(path, crop)
            logger.debug("疲劳 ROI 已保存: %s", path)

        raw_text = self._ocr_text(crop)
        current, max_value = self._parse_fatigue(raw_text)
        return FatigueResult(current=current, max_value=max_value, raw_text=raw_text)

    def crop_region(self, screen: np.ndarray) -> np.ndarray:
        height, width = screen.shape[:2]
        rx, ry, rw, rh = self.config.region
        x1 = max(0, int(rx * width))
        y1 = max(0, int(ry * height))
        x2 = min(width, int((rx + rw) * width))
        y2 = min(height, int((ry + rh) * height))
        return screen[y1:y2, x1:x2].copy()

    def _ocr_text(self, crop: np.ndarray) -> str:
        try:
            ocr = _get_ocr()
        except ImportError as exc:
            raise RuntimeError(
                "未安装 rapidocr-onnxruntime，请执行: pip install rapidocr-onnxruntime"
            ) from exc

        enlarged = cv2.resize(
            crop, None, fx=2.0, fy=2.0, interpolation=cv2.INTER_CUBIC
        )
        results, _ = ocr(enlarged)
        if not results:
            return ""
        return "".join(str(item[1]) for item in results)

    @staticmethod
    def _parse_fatigue(text: str) -> tuple[int | None, int | None]:
        cleaned = text.replace(" ", "")
        matches = list(_FATIGUE_PATTERN.finditer(cleaned))
        if not matches:
            return None, None

        # 优先取 max 值合理的匹配（避免把右侧能量 100 拼进来）
        for match in matches:
            current = int(match.group(1))
            max_value = int(match.group(2))
            if max_value <= 200:
                return current, max_value

        match = matches[0]
        return int(match.group(1)), int(match.group(2))
