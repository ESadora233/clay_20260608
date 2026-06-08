"""Windows PC 级鼠标/键盘输入。"""

from __future__ import annotations

import ctypes
import logging
import sys
import time
from ctypes import wintypes

from core.window_target import WindowTarget, resolve_window_target

logger = logging.getLogger(__name__)

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
INPUT_KEYBOARD = 1
KEYEVENTF_KEYUP = 0x0002
WM_LBUTTONDOWN = 0x0201
WM_LBUTTONUP = 0x0202
WM_MOUSEMOVE = 0x0200
WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101
MK_LBUTTON = 0x0001

PC_VK: dict[str, int] = {
    "left": 0x25,
    "up": 0x26,
    "right": 0x27,
    "down": 0x28,
    "enter": 0x0D,
    "space": 0x20,
    "w": 0x57,
}


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
    ]


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
    ]


class INPUT_UNION(ctypes.Union):
    _fields_ = [("mi", MOUSEINPUT), ("ki", KEYBDINPUT)]


class INPUT(ctypes.Structure):
    _fields_ = [("type", wintypes.DWORD), ("union", INPUT_UNION)]


def _require_windows() -> None:
    if sys.platform != "win32":
        raise RuntimeError("PC 输入仅支持 Windows")


def _lparam(x: int, y: int) -> int:
    return ((y & 0xFFFF) << 16) | (x & 0xFFFF)


def get_window_target(title_keywords: list[str]) -> WindowTarget:
    return resolve_window_target(title_keywords)


def focus_target(target: WindowTarget) -> None:
    _require_windows()
    hwnd = target.hwnd
    if not hwnd:
        return
    parent = user32.GetAncestor(hwnd, 2)
    focus_hwnd = int(parent) if parent else hwnd
    user32.ShowWindow(focus_hwnd, 9)
    foreground = user32.GetForegroundWindow()
    if foreground == focus_hwnd:
        time.sleep(0.05)
        return
    fg_thread = user32.GetWindowThreadProcessId(foreground, None)
    target_thread = user32.GetWindowThreadProcessId(focus_hwnd, None)
    current_thread = kernel32.GetCurrentThreadId()
    if fg_thread and target_thread:
        user32.AttachThreadInput(current_thread, fg_thread, True)
        user32.AttachThreadInput(target_thread, current_thread, True)
        user32.SetForegroundWindow(focus_hwnd)
        user32.AttachThreadInput(target_thread, current_thread, False)
        user32.AttachThreadInput(current_thread, fg_thread, False)
    else:
        user32.SetForegroundWindow(focus_hwnd)
    time.sleep(0.12)


def click_screen(x: int, y: int) -> None:
    _require_windows()
    user32.SetCursorPos(int(x), int(y))
    time.sleep(0.05)
    user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
    time.sleep(0.04)
    user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
    logger.info("物理点击 (%s, %s)", x, y)


def _screen_to_client(hwnd: int, screen_x: int, screen_y: int) -> tuple[int, int]:
    point = wintypes.POINT(int(screen_x), int(screen_y))
    if not user32.ScreenToClient(hwnd, ctypes.byref(point)):
        raise RuntimeError(f"ScreenToClient 失败 hwnd={hwnd}")
    return int(point.x), int(point.y)


def _post_click(hwnd: int, client_x: int, client_y: int) -> None:
    lp = _lparam(client_x, client_y)
    user32.PostMessageW(hwnd, WM_LBUTTONDOWN, MK_LBUTTON, lp)
    time.sleep(0.03)
    user32.PostMessageW(hwnd, WM_LBUTTONUP, 0, lp)


def click_at(
    target: WindowTarget | None,
    screen_x: int,
    screen_y: int,
    method: str = "physical",
) -> None:
    """method: physical | postmessage | both"""
    _require_windows()
    use_physical = method in {"physical", "both", "auto", ""}
    use_post = method in {"postmessage", "both"}

    if target and target.hwnd:
        focus_target(target)
        if use_physical:
            click_screen(screen_x, screen_y)
        if use_post:
            cx, cy = _screen_to_client(target.hwnd, screen_x, screen_y)
            _post_click(target.hwnd, cx, cy)
            logger.info(
                "PostMessage 点击 client(%s,%s) screen(%s,%s) hwnd=%s",
                cx,
                cy,
                screen_x,
                screen_y,
                target.hwnd,
            )
        return

    click_screen(screen_x, screen_y)


def drag_screen(x1: int, y1: int, x2: int, y2: int, steps: int = 12) -> None:
    _require_windows()
    user32.SetCursorPos(int(x1), int(y1))
    time.sleep(0.05)
    user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
    for i in range(1, steps + 1):
        nx = int(x1 + (x2 - x1) * i / steps)
        ny = int(y1 + (y2 - y1) * i / steps)
        user32.SetCursorPos(nx, ny)
        time.sleep(0.025)
    user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
    logger.info("物理拖动 (%s,%s) -> (%s,%s)", x1, y1, x2, y2)


def drag_at(
    target: WindowTarget | None,
    screen_x1: int,
    screen_y1: int,
    screen_x2: int,
    screen_y2: int,
    steps: int = 12,
    method: str = "physical",
) -> None:
    _require_windows()
    use_physical = method in {"physical", "both", "auto", ""}
    use_post = method in {"postmessage", "both"}

    if target and target.hwnd:
        focus_target(target)
        if use_physical:
            drag_screen(screen_x1, screen_y1, screen_x2, screen_y2, steps=steps)
        if use_post:
            hwnd = target.hwnd
            cx1, cy1 = _screen_to_client(hwnd, screen_x1, screen_y1)
            cx2, cy2 = _screen_to_client(hwnd, screen_x2, screen_y2)
            user32.PostMessageW(hwnd, WM_LBUTTONDOWN, MK_LBUTTON, _lparam(cx1, cy1))
            time.sleep(0.03)
            for i in range(1, steps + 1):
                nx = int(cx1 + (cx2 - cx1) * i / steps)
                ny = int(cy1 + (cy2 - cy1) * i / steps)
                user32.PostMessageW(hwnd, WM_MOUSEMOVE, MK_LBUTTON, _lparam(nx, ny))
                time.sleep(0.02)
            user32.PostMessageW(hwnd, WM_LBUTTONUP, 0, _lparam(cx2, cy2))
        return

    drag_screen(screen_x1, screen_y1, screen_x2, screen_y2, steps=steps)


def _send_input_vk(vk: int, key_up: bool = False) -> None:
    inp = INPUT()
    inp.type = INPUT_KEYBOARD
    inp.union.ki = KEYBDINPUT(
        wVk=vk,
        wScan=0,
        dwFlags=KEYEVENTF_KEYUP if key_up else 0,
        time=0,
        dwExtraInfo=None,
    )
    if user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT)) != 1:
        raise RuntimeError(f"SendInput 失败 vk={vk}")


def press_vk(name: str, target: WindowTarget | None = None) -> None:
    key = name.strip().lower()
    vk = PC_VK.get(key)
    if vk is None:
        raise ValueError(f"PC 不支持按键: {name}")
    if target and target.hwnd:
        focus_target(target)
    _send_input_vk(vk, False)
    time.sleep(0.04)
    _send_input_vk(vk, True)
    logger.info("SendInput 按键 %s", name)


def click_target_center(target: WindowTarget) -> None:
    cx = target.left + target.width // 2
    cy = target.top + target.height // 2
    click_at(target, cx, cy)
