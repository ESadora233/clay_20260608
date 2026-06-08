"""屏幕截图（ADB 或 PC 窗口）。"""

from __future__ import annotations

import logging
from io import BytesIO
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

from core.adb import AdbClient, AdbError
from core.adb_display import resolve_touch_size
from core.screen_utils import is_blank_screen
from core.window_capture import WindowCaptureError, grab_window_with_target
from core.window_target import WindowTarget

logger = logging.getLogger(__name__)

BLANK_SCREEN_HINT = (
    "截图全黑，ADB 无法捕获应用宝画面。请尝试:\n"
    "1. config.yaml 设置 capture.mode: window\n"
    "2. 在 config.yaml 设置 capture.window_rect\n"
    "3. 运行 python main.py pick-window"
)


class CaptureError(RuntimeError):
    pass


class ScreenCapture:
    def __init__(
        self,
        adb: AdbClient,
        temp_dir: str | Path = "runtime/screenshots",
        mode: str = "adb",
        window_titles: list[str] | None = None,
        window_rect: tuple[int, int, int, int] | None = None,
        client_offset: tuple[int, int] = (0, 0),
        blank_threshold: float = 1.0,
        adb_fallback_to_window: bool = True,
    ) -> None:
        self.adb = adb
        self.temp_dir = Path(temp_dir)
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        self.mode = mode.strip().lower()
        self.window_titles = window_titles or ["地下城", "勇士", "应用宝"]
        self.window_rect = window_rect
        self.client_offset = client_offset
        self.blank_threshold = blank_threshold
        self.adb_fallback_to_window = adb_fallback_to_window

        self._capture_w = 0
        self._capture_h = 0
        self._device_w = 0
        self._device_h = 0
        self._using_window = self.mode == "window"
        self._target: WindowTarget | None = None
        self._refresh_device_size()

    @property
    def using_window(self) -> bool:
        return self._using_window

    @property
    def target(self) -> WindowTarget | None:
        return self._target

    def map_to_device(self, x: int, y: int) -> tuple[int, int]:
        if self._device_w <= 0 or self._capture_w <= 0:
            return x, y
        dx = int(x * self._device_w / self._capture_w)
        dy = int(y * self._device_h / self._capture_h)
        return dx, dy

    def to_screen_coords(self, x: int, y: int) -> tuple[int, int]:
        if not self._target:
            ox, oy = self.client_offset
            return ox + x, oy + y
        ox, oy = self.client_offset
        sx = self._target.left + ox + int(x * self._target.width / max(self._capture_w, 1))
        sy = self._target.top + oy + int(y * self._target.height / max(self._capture_h, 1))
        return sx, sy

    def focus_window(self) -> None:
        from core.pc_input import click_target_center, focus_target

        if self._target and self._target.hwnd:
            focus_target(self._target)
            click_target_center(self._target)
        elif self._target:
            cx = self._target.left + self._target.width // 2
            cy = self._target.top + self._target.height // 2
            from core.pc_input import click_screen

            click_screen(cx, cy)

    def grab(self, save_debug: bool = False) -> np.ndarray:
        if self.mode == "window":
            bgr = self._grab_window()
        else:
            bgr = self._grab_adb()
            if is_blank_screen(bgr, self.blank_threshold):
                if self.adb_fallback_to_window:
                    logger.warning("ADB 截图为黑屏，自动切换为窗口截图")
                    bgr = self._grab_window()
                    self._using_window = True
                else:
                    raise CaptureError(BLANK_SCREEN_HINT)

        if is_blank_screen(bgr, self.blank_threshold):
            raise CaptureError(BLANK_SCREEN_HINT)

        self._capture_h, self._capture_w = bgr.shape[:2]
        self._refresh_device_size()
        if save_debug:
            debug_path = self.temp_dir / "latest.png"
            cv2.imwrite(str(debug_path), bgr)
            logger.debug("调试截图已保存: %s (%sx%s)", debug_path, self._capture_w, self._capture_h)

        return bgr

    def _refresh_device_size(self) -> None:
        try:
            self.adb.ensure_connected()
            w, h = resolve_touch_size(self.adb)
            self._device_w = w
            self._device_h = h
        except AdbError:
            pass

    def _grab_adb(self) -> np.ndarray:
        self.adb.ensure_connected()
        png_bytes = self.adb.exec_out("screencap", "-p")
        if not png_bytes.startswith(b"\x89PNG"):
            png_bytes = png_bytes.replace(b"\r\n", b"\n")
        image = Image.open(BytesIO(png_bytes))
        rgb = np.array(image.convert("RGB"))
        return cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)

    def _grab_window(self) -> np.ndarray:
        try:
            bgr, target = grab_window_with_target(self.window_titles, fixed_rect=self.window_rect)
            self._target = target
            self._using_window = True
            return bgr
        except WindowCaptureError as exc:
            raise CaptureError(str(exc)) from exc
