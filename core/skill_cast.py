"""释放 W 技能（点击 + 按键）。"""

from __future__ import annotations

import logging
import time

from core.config import DungeonSettings
from core.input import InputController

logger = logging.getLogger(__name__)


def skill_w_ratio(settings: DungeonSettings) -> tuple[float, float]:
    rx = settings.skill_w_ratio[0] + settings.skill_w_offset[0]
    ry = settings.skill_w_ratio[1] + settings.skill_w_offset[1]
    return max(0.0, min(1.0, rx)), max(0.0, min(1.0, ry))


def cast_skill_w(
    input_ctrl: InputController,
    settings: DungeonSettings,
    screen,
    *,
    mapper=None,
    capture=None,
) -> None:
    if capture is not None:
        capture.focus_window()
        time.sleep(0.15)

    method = settings.skill_method.strip().lower()
    use_tap = settings.use_skill_tap and method in {"tap", "both", "auto", ""}
    use_key = settings.use_skill_key and method in {"key", "both", "auto", ""}

    rx, ry = skill_w_ratio(settings)
    if use_tap:
        for i in range(max(1, settings.skill_tap_times)):
            input_ctrl.tap_ratio(screen, rx, ry, delay=False, mapper=mapper)
            logger.info("点击 W 技能 (%s, %s) 第 %s 次", rx, ry, i + 1)
            if i + 1 < settings.skill_tap_times:
                time.sleep(settings.skill_tap_interval)
        time.sleep(0.1)

    if use_key:
        input_ctrl.press_key("w", times=1, delay=False)
        logger.info("发送 W 按键")

    time.sleep(input_ctrl.action_delay)
