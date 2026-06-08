"""应用宝模拟器两种操作模式：键盘模式 / 鼠标模式。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ModePreset:
    movement_method: str
    skill_method: str
    use_skill_tap: bool
    use_skill_key: bool
    nudge_method: str
    description: str


MODE_PRESETS: dict[str, ModePreset] = {
    "keyboard": ModePreset(
        movement_method="key",
        skill_method="key",
        use_skill_tap=False,
        use_skill_key=True,
        nudge_method="key",
        description="无移动轮盘，方向键移动，W 键放技能",
    ),
    "mouse": ModePreset(
        movement_method="swipe",
        skill_method="tap",
        use_skill_tap=True,
        use_skill_key=False,
        nudge_method="swipe",
        description="左侧轮盘滑动移动，鼠标点击技能",
    ),
}


def apply_emulator_mode(mode: str, movement: Any, dungeon: Any) -> ModePreset | None:
    """按模式覆盖移动/技能/微移策略。mode=custom 时不覆盖。"""
    key = mode.strip().lower()
    if key in {"", "custom"}:
        return None
    preset = MODE_PRESETS.get(key)
    if preset is None:
        raise ValueError(f"未知 emulator_mode: {mode}，可用: keyboard, mouse, custom")

    movement.method = preset.movement_method
    dungeon.skill_method = preset.skill_method
    dungeon.use_skill_tap = preset.use_skill_tap
    dungeon.use_skill_key = preset.use_skill_key
    dungeon.nudge_method = preset.nudge_method
    return preset
