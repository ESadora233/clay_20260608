"""解析 Android 真实触控分辨率（应用宝 wm size 常为 480x320，但 app 为 2560x1440）。"""

from __future__ import annotations

import logging
import re

from core.adb import AdbClient, AdbError

logger = logging.getLogger(__name__)

_APP_SIZE_RE = re.compile(r"app=(\d+)x(\d+)")
_OVERRIDE_SIZE_RE = re.compile(r"Override size:\s*(\d+)x(\d+)", re.IGNORECASE)
_PHYSICAL_SIZE_RE = re.compile(r"Physical size:\s*(\d+)x(\d+)", re.IGNORECASE)


def resolve_touch_size(adb: AdbClient) -> tuple[int, int]:
    """返回 ADB input tap/swipe 应使用的坐标系宽高。"""
    adb.ensure_connected()

    best: tuple[int, int] | None = None
    try:
        displays = adb.shell("dumpsys", "window", "displays", check=False)
        text = (displays.stdout or "") + (displays.stderr or "")
        for w_str, h_str in _APP_SIZE_RE.findall(text):
            w, h = int(w_str), int(h_str)
            if w >= 720 and h >= 480:
                if best is None or w * h > best[0] * best[1]:
                    best = (w, h)
        if best:
            logger.debug("触控分辨率(app): %sx%s", best[0], best[1])
            return best
    except AdbError:
        pass

    try:
        wm = adb.shell("wm", "size", check=False)
        text = (wm.stdout or "") + (wm.stderr or "")
        override = _OVERRIDE_SIZE_RE.search(text)
        if override:
            w, h = int(override.group(1)), int(override.group(2))
            logger.debug("触控分辨率(override): %sx%s", w, h)
            return w, h
        physical = _PHYSICAL_SIZE_RE.search(text)
        if physical:
            w, h = int(physical.group(1)), int(physical.group(2))
            logger.debug("触控分辨率(physical): %sx%s", w, h)
            return w, h
    except AdbError:
        pass

    return 480, 320
