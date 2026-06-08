"""Android 常用按键码（adb shell input keyevent）。"""

from __future__ import annotations

# 方向键 / 小键盘
KEYCODE_DPAD_UP = 19
KEYCODE_DPAD_DOWN = 20
KEYCODE_DPAD_LEFT = 21
KEYCODE_DPAD_RIGHT = 22

# 常用别名
KEY_RIGHT = KEYCODE_DPAD_RIGHT
KEY_LEFT = KEYCODE_DPAD_LEFT
KEY_UP = KEYCODE_DPAD_UP
KEY_DOWN = KEYCODE_DPAD_DOWN
KEY_BACK = 4
KEY_ENTER = 66
KEY_SPACE = 62
KEYCODE_W = 113

DIRECTION_ALIASES: dict[str, int] = {
    "up": KEY_UP,
    "down": KEY_DOWN,
    "left": KEY_LEFT,
    "right": KEY_RIGHT,
    "enter": KEY_ENTER,
    "space": KEY_SPACE,
    "back": KEY_BACK,
    "w": KEYCODE_W,
}


def resolve_key(name: str) -> int:
    key = name.strip().lower()
    if key in DIRECTION_ALIASES:
        return DIRECTION_ALIASES[key]
    if key.isdigit():
        return int(key)
    raise ValueError(f"未知按键: {name}，可用: {', '.join(DIRECTION_ALIASES)}")
