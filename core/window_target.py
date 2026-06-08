"""定位游戏渲染子窗口（应用宝 Androws 内核）。"""

from __future__ import annotations

import ctypes
import logging
from ctypes import wintypes
from dataclasses import dataclass

logger = logging.getLogger(__name__)

user32 = ctypes.windll.user32


@dataclass
class WindowTarget:
    hwnd: int
    left: int
    top: int
    width: int
    height: int
    title: str
    parent_title: str = ""
    class_name: str = ""

    @property
    def rect(self) -> tuple[int, int, int, int]:
        return self.left, self.top, self.width, self.height


def _window_text(hwnd: int) -> str:
    length = user32.GetWindowTextLengthW(hwnd)
    if length <= 0:
        return ""
    buff = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, buff, length + 1)
    return buff.value.strip()


def _window_rect(hwnd: int) -> tuple[int, int, int, int]:
    rect = wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(rect))
    return rect.left, rect.top, rect.right - rect.left, rect.bottom - rect.top


def _window_class(hwnd: int) -> str:
    buff = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(hwnd, buff, 256)
    return buff.value.strip()


def _match_score(title: str, keywords: list[str]) -> int:
    lower = title.lower()
    score = 0
    for kw in keywords:
        if kw.lower() in lower:
            score += 10
    for hint in ("地下城", "勇士", "起源", "dnf", "androws", "应用宝", "腾讯"):
        if hint.lower() in lower:
            score += 3
    return score


def find_parent_hwnd(title_keywords: list[str]) -> tuple[int, str, tuple[int, int, int, int]]:
    keywords = [k for k in title_keywords if k.strip()]
    best: tuple[int, str, tuple[int, int, int, int], int] | None = None

    def callback(hwnd, _lparam):
        nonlocal best
        if not user32.IsWindowVisible(hwnd):
            return True
        title = _window_text(hwnd)
        if not title:
            return True
        score = _match_score(title, keywords)
        if score <= 0:
            return True
        rect = _window_rect(hwnd)
        if rect[2] < 200 or rect[3] < 200:
            return True
        total = score * 1000000 + rect[2] * rect[3]
        if best is None or total > best[3]:
            best = (int(hwnd), title, rect, total)
        return True

    enum_proc = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)(callback)
    user32.EnumWindows(enum_proc, 0)
    if best is None:
        raise RuntimeError(f"未找到父窗口，关键词: {title_keywords}")
    return best[0], best[1], best[2]


def _list_child_targets(parent_hwnd: int) -> list[WindowTarget]:
    parent_title = _window_text(parent_hwnd)
    children: list[WindowTarget] = []

    def callback(hwnd, _lparam):
        if not user32.IsWindowVisible(hwnd):
            return True
        left, top, width, height = _window_rect(hwnd)
        if width < 200 or height < 200:
            return True
        title = _window_text(hwnd)
        children.append(
            WindowTarget(
                hwnd=int(hwnd),
                left=left,
                top=top,
                width=width,
                height=height,
                title=title or "(child)",
                parent_title=parent_title,
                class_name=_window_class(hwnd),
            )
        )
        return True

    enum_proc = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)(callback)
    user32.EnumChildWindows(parent_hwnd, enum_proc, 0)
    return children


def resolve_window_target(
    title_keywords: list[str],
    fixed_rect: tuple[int, int, int, int] | None = None,
) -> WindowTarget:
    """优先使用 Androws 子窗口（真正接收鼠标/键盘的区域）。"""
    if fixed_rect:
        left, top, width, height = fixed_rect
        return WindowTarget(
            hwnd=0,
            left=left,
            top=top,
            width=width,
            height=height,
            title="window_rect",
        )

    parent_hwnd, parent_title, _parent_rect = find_parent_hwnd(title_keywords)
    children = _list_child_targets(parent_hwnd)

    if children:
        def child_rank(t: WindowTarget) -> tuple[int, int]:
            name = t.title.lower()
            cls = t.class_name.lower()
            bonus = 0
            if cls == "subwin" or name == "sub":
                bonus += 300
            elif "androws" in name:
                bonus += 100
            return bonus, t.width * t.height

        target = max(children, key=child_rank)
        logger.info(
            "使用子窗口: %s (%sx%s) @ (%s,%s)，父窗口: %s",
            target.title,
            target.width,
            target.height,
            target.left,
            target.top,
            parent_title,
        )
        return target

    left, top, width, height = _window_rect(parent_hwnd)
    logger.warning("未找到子窗口，回退父窗口: %s", parent_title)
    return WindowTarget(
        hwnd=parent_hwnd,
        left=left,
        top=top,
        width=width,
        height=height,
        title=parent_title,
        parent_title=parent_title,
    )
