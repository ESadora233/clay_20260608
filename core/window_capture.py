"""通过 PC 窗口截取模拟器画面（应用宝 ADB 黑屏时使用）。"""

from __future__ import annotations

import ctypes
import logging
import sys
from ctypes import wintypes

import cv2
import mss
import numpy as np

from core.window_target import WindowTarget, resolve_window_target

logger = logging.getLogger(__name__)

user32 = ctypes.windll.user32


class WindowCaptureError(RuntimeError):
    pass


def _iter_visible_windows(title_keywords: list[str]) -> list[tuple[int, int, int, int, str]]:
    if sys.platform != "win32":
        raise WindowCaptureError("窗口截图仅支持 Windows")

    keywords = [k.lower() for k in title_keywords if k.strip()]
    matches: list[tuple[int, int, int, int, str]] = []

    def callback(hwnd, _lparam):
        if not user32.IsWindowVisible(hwnd):
            return True
        length = user32.GetWindowTextLengthW(hwnd)
        if length <= 0:
            return True
        buff = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buff, length + 1)
        title = buff.value.strip()
        if not title:
            return True
        lower = title.lower()
        if keywords and not any(k in lower for k in keywords):
            return True
        rect = wintypes.RECT()
        user32.GetWindowRect(hwnd, ctypes.byref(rect))
        width = rect.right - rect.left
        height = rect.bottom - rect.top
        if width < 200 or height < 200:
            return True
        matches.append((rect.left, rect.top, width, height, title))
        return True

    enum_proc = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)(callback)
    user32.EnumWindows(enum_proc, 0)
    return matches


def list_visible_windows() -> list[tuple[int, int, int, int, str]]:
    windows = sorted(_iter_visible_windows([""]), key=lambda item: item[2] * item[3], reverse=True)
    skip = {"program manager", "windows 输入体验", "windows input experience", "cursor", "powershell"}
    filtered: list[tuple[int, int, int, int, str]] = []
    for item in windows:
        title = item[4].lower()
        if any(s in title for s in skip):
            continue
        filtered.append(item)
    return filtered or windows


def score_window(title: str, keywords: list[str]) -> int:
    lower = title.lower()
    score = 0
    for kw in keywords:
        if not kw.strip():
            continue
        if kw.lower() in lower:
            score += 10
    game_hints = ["地下城", "勇士", "起源", "dnf", "手游", "模拟", "androws", "应用宝", "腾讯", "tencent"]
    for hint in game_hints:
        if hint.lower() in lower:
            score += 5
    return score


def find_window_rect(title_keywords: list[str]) -> tuple[int, int, int, int, str]:
    target = resolve_window_target(title_keywords)
    return target.left, target.top, target.width, target.height, target.title


def grab_window_rect(left: int, top: int, width: int, height: int) -> np.ndarray:
    monitor = {"left": left, "top": top, "width": width, "height": height}
    with mss.mss() as sct:
        shot = sct.grab(monitor)
        bgra = np.array(shot)
        return cv2.cvtColor(bgra, cv2.COLOR_BGRA2BGR)


def grab_window(title_keywords: list[str], fixed_rect: tuple[int, int, int, int] | None = None) -> np.ndarray:
    image, _target = grab_window_with_target(title_keywords, fixed_rect=fixed_rect)
    return image


def grab_window_with_target(
    title_keywords: list[str],
    fixed_rect: tuple[int, int, int, int] | None = None,
) -> tuple[np.ndarray, WindowTarget]:
    target = resolve_window_target(title_keywords, fixed_rect=fixed_rect)
    image = grab_window_rect(*target.rect)
    return image, target
