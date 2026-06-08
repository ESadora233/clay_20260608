"""读写 config.yaml 中的 UI 点击坐标。"""

from __future__ import annotations

PICK_POINT_NAMES: dict[str, str] = {
    "gear": "settings_gear",
    "settings_gear": "settings_gear",
    "unstuck": "unstuck",
    "close": "settings_close",
    "settings_close": "settings_close",
    "return": "return_town",
    "return_town": "return_town",
    "confirm": "confirm_leave",
    "confirm_leave": "confirm_leave",
    "blocked_trial": "blocked_trial",
    "map_first": "map_first",
    "start_battle": "start_battle",
    "w": "skill_w",
    "skill_w": "skill_w",
}

PICK_POINT_LABELS: dict[str, str] = {
    "settings_gear": "右上角齿轮",
    "unstuck": "脱离卡死",
    "settings_close": "关闭设置叉号",
    "return_town": "返回城镇",
    "confirm_leave": "确认离开",
    "blocked_trial": "封锁的试验场",
    "map_first": "第一个地图",
    "start_battle": "战斗开始",
    "skill_w": "W 技能",
}


def resolve_pick_name(name: str) -> str:
    key = name.strip().lower()
    if key not in PICK_POINT_NAMES:
        known = ", ".join(sorted(set(PICK_POINT_NAMES.keys())))
        raise ValueError(f"未知标定点: {name}，可用: {known}")
    return PICK_POINT_NAMES[key]
