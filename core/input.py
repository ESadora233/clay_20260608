"""点击与按键：支持 ADB / PC / 混合模式。"""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING

from core.adb import AdbClient
from core.keycodes import resolve_key

if TYPE_CHECKING:
    from core.capture import ScreenCapture

logger = logging.getLogger(__name__)


class InputController:
    def __init__(
        self,
        adb: AdbClient,
        action_delay: float = 0.5,
        capture: ScreenCapture | None = None,
        input_mode: str = "hybrid",
        pc_method: str = "physical",
    ) -> None:
        self.adb = adb
        self.action_delay = action_delay
        self.capture = capture
        self.input_mode = input_mode.strip().lower()
        self.pc_method = pc_method.strip().lower() or "physical"

    def _mode_pc(self) -> bool:
        return self.input_mode in {"auto", "window", "hybrid"}

    def _mode_adb(self) -> bool:
        return self.input_mode in {"adb", "hybrid"}

    def _mode_hybrid(self) -> bool:
        return self.input_mode == "hybrid" or (
            self.input_mode == "auto" and self.capture and self.capture.using_window
        )

    def _use_pc_input(self) -> bool:
        if self.input_mode == "adb":
            return False
        if self.input_mode in {"window", "hybrid"}:
            return True
        return bool(self.capture and self.capture.using_window)

    def _get_target(self):
        if not self.capture:
            return None
        from core.pc_input import get_window_target

        return self.capture.target or get_window_target(self.capture.window_titles)

    def _prepare_focus(self) -> None:
        if not self.capture or not self._use_pc_input():
            return
        from core.pc_input import focus_target

        target = self._get_target()
        if target and target.hwnd:
            focus_target(target)

    def _adb_tap(self, x: int, y: int, mapper=None) -> None:
        if mapper is not None:
            x, y = mapper(x, y)
        self.adb.ensure_connected()
        self.adb.shell("input", "tap", str(x), str(y))
        logger.info("ADB 点击 (%s, %s)", x, y)

    def _adb_key(self, name: str) -> None:
        keycode = resolve_key(name)
        self.adb.ensure_connected()
        self.adb.shell("input", "keyevent", str(keycode))
        logger.info("ADB 按键 %s (keycode=%s)", name, keycode)

    def tap(self, x: int, y: int, delay: bool = True, mapper=None) -> None:
        dx, dy = x, y
        if mapper is not None:
            dx, dy = mapper(x, y)
        elif self.capture:
            dx, dy = self.capture.map_to_device(x, y)

        if self._use_pc_input() and self.capture:
            from core.pc_input import click_at

            self._prepare_focus()
            sx, sy = self.capture.to_screen_coords(x, y)
            click_at(self._get_target(), sx, sy, method=self.pc_method)

        if self._mode_adb():
            self.adb.ensure_connected()
            self.adb.shell("input", "tap", str(dx), str(dy))
            logger.info("ADB 点击 (%s, %s)", dx, dy)

        if delay:
            time.sleep(self.action_delay)

    def swipe_ratio(
        self,
        screen,
        x1: float,
        y1: float,
        x2: float,
        y2: float,
        duration_ms: int = 300,
        delay: bool = True,
        mapper=None,
    ) -> None:
        height, width = screen.shape[:2]
        self.swipe(
            int(x1 * width),
            int(y1 * height),
            int(x2 * width),
            int(y2 * height),
            duration_ms=duration_ms,
            delay=delay,
            mapper=mapper,
        )

    def swipe(
        self,
        x1: int,
        y1: int,
        x2: int,
        y2: int,
        duration_ms: int = 300,
        delay: bool = True,
        mapper=None,
    ) -> None:
        if self._use_pc_input() and self.capture:
            from core.pc_input import drag_at

            self._prepare_focus()
            sx1, sy1 = self.capture.to_screen_coords(x1, y1)
            sx2, sy2 = self.capture.to_screen_coords(x2, y2)
            drag_at(self._get_target(), sx1, sy1, sx2, sy2, method=self.pc_method)

        if self._mode_adb():
            ax1, ay1 = (mapper(x1, y1) if mapper else (x1, y1))
            ax2, ay2 = (mapper(x2, y2) if mapper else (x2, y2))
            if self.capture and self._use_pc_input():
                ax1, ay1 = self.capture.map_to_device(x1, y1)
                ax2, ay2 = self.capture.map_to_device(x2, y2)
            self.adb.ensure_connected()
            self.adb.shell(
                "input", "swipe",
                str(ax1), str(ay1), str(ax2), str(ay2), str(duration_ms),
            )
            logger.info("ADB 滑动 (%s,%s) -> (%s,%s)", ax1, ay1, ax2, ay2)

        if delay:
            time.sleep(self.action_delay)

    def press_key(
        self,
        name: str,
        times: int = 1,
        interval: float | None = None,
        delay: bool = True,
    ) -> None:
        gap = self.action_delay if interval is None else interval
        for i in range(times):
            if self._use_pc_input():
                from core.pc_input import press_vk

                self._prepare_focus()
                try:
                    press_vk(name, target=self._get_target())
                except Exception as exc:
                    logger.warning("PC 按键失败: %s", exc)

            if self._mode_adb():
                try:
                    self._adb_key(name)
                except Exception as exc:
                    logger.warning("ADB 按键失败: %s", exc)

            if i < times - 1:
                time.sleep(gap)

        if delay:
            time.sleep(self.action_delay)

    def press_right(self, times: int = 1, interval: float | None = None, delay: bool = True) -> None:
        self.press_key("right", times=times, interval=interval, delay=delay)

    def press_left(self, times: int = 1, interval: float | None = None, delay: bool = True) -> None:
        self.press_key("left", times=times, interval=interval, delay=delay)

    def tap_ratio(self, screen, rx: float, ry: float, delay: bool = True, mapper=None) -> None:
        height, width = screen.shape[:2]
        self.tap(int(rx * width), int(ry * height), delay=delay, mapper=mapper)

    def back(self) -> None:
        if self._mode_adb():
            self._adb_key("back")
        else:
            self.press_key("back")

    def home(self) -> None:
        self._adb_key("home") if self._mode_adb() else None
