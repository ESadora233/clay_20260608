"""OpenCV 模板匹配。"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class MatchResult:
    name: str
    confidence: float
    top_left: tuple[int, int]
    bottom_right: tuple[int, int]
    center: tuple[int, int]

    @property
    def found(self) -> bool:
        return self.confidence > 0


class TemplateMatcher:
    def __init__(self, templates_dir: str | Path, threshold: float = 0.85) -> None:
        self.templates_dir = Path(templates_dir)
        self.threshold = threshold
        self._cache: dict[str, np.ndarray] = {}

    def load_template(self, name: str) -> np.ndarray:
        if name in self._cache:
            return self._cache[name]

        path = self.templates_dir / name
        if not path.exists():
            raise FileNotFoundError(f"模板不存在: {path}")

        template = cv2.imread(str(path), cv2.IMREAD_COLOR)
        if template is None:
            raise ValueError(f"无法读取模板: {path}")

        self._cache[name] = template
        return template

    def find(
        self,
        screen: np.ndarray,
        template_name: str,
        threshold: float | None = None,
    ) -> MatchResult | None:
        template = self.load_template(template_name)
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(
            cv2.matchTemplate(screen, template, cv2.TM_CCOEFF_NORMED)
        )

        use_threshold = self.threshold if threshold is None else threshold
        if max_val < use_threshold:
            return None

        h, w = template.shape[:2]
        x, y = max_loc
        center = (x + w // 2, y + h // 2)
        return MatchResult(
            name=template_name,
            confidence=float(max_val),
            top_left=(x, y),
            bottom_right=(x + w, y + h),
            center=center,
        )

    def find_any(
        self,
        screen: np.ndarray,
        template_names: list[str],
        threshold: float | None = None,
    ) -> MatchResult | None:
        best: MatchResult | None = None
        for name in template_names:
            result = self.find(screen, name, threshold=threshold)
            if result and (best is None or result.confidence > best.confidence):
                best = result
        return best

    def wait_for(
        self,
        grab_screen,
        template_name: str,
        timeout: float,
        poll_interval: float,
        threshold: float | None = None,
    ) -> MatchResult:
        """轮询截图直到模板出现或超时。"""
        import time

        deadline = time.time() + timeout
        while time.time() < deadline:
            screen = grab_screen()
            result = self.find(screen, template_name, threshold=threshold)
            if result:
                logger.info(
                    "匹配成功 %s confidence=%.3f center=%s",
                    template_name,
                    result.confidence,
                    result.center,
                )
                return result
            time.sleep(poll_interval)

        raise TimeoutError(f"等待模板超时: {template_name} ({timeout}s)")
