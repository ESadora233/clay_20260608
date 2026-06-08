"""等待进图加载完成（HP/MP 球出现 + 画面稳定）。"""

from __future__ import annotations

import logging
import time
from typing import Callable

import numpy as np

from core.config import DungeonSettings
from core.skill_cast import skill_w_ratio

logger = logging.getLogger(__name__)


def _hp_mp_visible(screen: np.ndarray) -> bool:
    h, w = screen.shape[:2]
    left = screen[int(h * 0.84) : int(h * 0.96), int(w * 0.30) : int(w * 0.42)]
    right = screen[int(h * 0.84) : int(h * 0.96), int(w * 0.58) : int(w * 0.70)]
    if left.size == 0 or right.size == 0:
        return False
    red_score = float(left[:, :, 2].mean()) - float(left[:, :, 0].mean())
    blue_score = float(right[:, :, 0].mean()) - float(right[:, :, 2].mean())
    return red_score > 25 and blue_score > 25


def _skill_bar_visible(screen: np.ndarray, dungeon: DungeonSettings) -> bool:
    h, w = screen.shape[:2]
    rx, ry = skill_w_ratio(dungeon)
    cx, cy = int(rx * w), int(ry * h)
    pad = max(18, int(min(w, h) * 0.02))
    patch = screen[
        max(0, cy - pad) : min(h, cy + pad),
        max(0, cx - pad) : min(w, cx + pad),
    ]
    if patch.size == 0:
        return False
    return float(patch.mean()) > 35 and float(patch.std()) > 12


def is_battle_ui_ready(screen: np.ndarray, dungeon: DungeonSettings) -> bool:
    return _hp_mp_visible(screen) and _skill_bar_visible(screen, dungeon)


def wait_battle_ready(
    grab: Callable[[], np.ndarray],
    dungeon: DungeonSettings,
) -> np.ndarray:
    """进图后轮询，直到战斗 HUD 出现再返回最新截图。"""
    logger.info("等待战斗加载完成（至少 %.1fs）…", dungeon.after_enter_wait)
    time.sleep(dungeon.after_enter_wait)

    deadline = time.time() + dungeon.battle_ready_timeout
    prev: np.ndarray | None = None
    stable_rounds = 0

    while time.time() < deadline:
        screen = grab()
        if is_battle_ui_ready(screen, dungeon):
            logger.info("战斗 HUD 已就绪（HP/MP + 技能栏可见）")
            time.sleep(dungeon.battle_ready_settle)
            return grab()

        if prev is not None:
            diff = float(np.abs(screen.astype(np.int16) - prev.astype(np.int16)).mean())
            if diff < 2.5:
                stable_rounds += 1
            else:
                stable_rounds = 0
            if stable_rounds >= 3 and _hp_mp_visible(screen):
                logger.info("画面已稳定且 HP/MP 可见")
                time.sleep(dungeon.battle_ready_settle)
                return grab()

        prev = screen
        time.sleep(dungeon.battle_ready_poll)

    logger.warning(
        "等待战斗就绪超时 (%.0fs)，仍将尝试释放技能",
        dungeon.battle_ready_timeout,
    )
    return grab()
