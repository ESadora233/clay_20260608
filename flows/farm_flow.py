"""
DNF 手游搬砖流程

主城 → 滑动移动 → 选关 → 封锁的试验场 → 选图 → 战斗开始
进图后 → W → 齿轮 → 脱离卡死 → 回城
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from pathlib import Path

from core.capture import ScreenCapture
from core.config import AppConfig
from core.fatigue import FatigueConfig, FatigueReader
from core.input import InputController
from core.matcher import MatchResult, TemplateMatcher
from core.battle_ready import wait_battle_ready
from core.skill_cast import cast_skill_w
from core.state_machine import StateMachine

logger = logging.getLogger(__name__)

TEMPLATES = {
    "main_city": "main_city.png",
    "dungeon_select": "dungeon_select.png",
    "blocked_trial": "blocked_trial.png",
    "dungeon_detail": "dungeon_detail.png",
    "map_first": "map_first.png",
    "start_battle": "start_battle.png",
    "in_dungeon": "in_dungeon.png",
    "settings_gear": "settings_gear.png",
    "unstuck": "unstuck.png",
    "settings_close": "settings_close.png",
    "return_town": "return_town.png",
    "confirm_leave": "confirm_leave.png",
    "confirm": "confirm.png",
    "settlement": "settlement.png",
}


@dataclass
class FarmContext:
    max_rounds: int = 0
    rounds: int = 0
    max_failures: int = 5
    failures: int = 0
    last_state: str = "scan"
    last_fatigue: int | None = None
    moved_right: bool = False
    dungeon_step: int = 0


def build_farm_flow(
    config: AppConfig,
    capture: ScreenCapture,
    matcher: TemplateMatcher,
    input_ctrl: InputController,
    max_rounds: int = 0,
) -> StateMachine:
    ctx = FarmContext(max_rounds=max_rounds)
    fatigue_reader = FatigueReader(
        FatigueConfig(
            enabled=config.fatigue.enabled,
            stop_at=config.fatigue.stop_at,
            region=config.fatigue.region,
        ),
        debug_dir=config.temp_dir,
    )
    mapper = capture.map_to_device if not input_ctrl._use_pc_input() else None
    dungeon = config.dungeon

    def grab():
        return capture.grab(save_debug=True)

    def battle_prepare() -> None:
        capture.focus_window()
        time.sleep(0.12)

    def battle_pause() -> None:
        time.sleep(dungeon.battle_step_delay)

    def template_path(template_key: str) -> Path:
        name = TEMPLATES.get(template_key, template_key)
        if not name.endswith(".png"):
            name = f"{name}.png"
        return Path(config.templates_dir) / name

    def has_template(template_key: str) -> bool:
        return template_path(template_key).is_file()

    def find_template(screen, template_key: str) -> MatchResult | None:
        if not has_template(template_key):
            return None
        return matcher.find(screen, template_path(template_key).name)

    def tap_match(result: MatchResult) -> None:
        input_ctrl.tap(*result.center, mapper=mapper)

    def tap_ratio(rx: float, ry: float, screen=None) -> None:
        if screen is None:
            screen = grab()
        input_ctrl.tap_ratio(screen, rx, ry, mapper=mapper)

    def check_fatigue() -> str | None:
        if not config.fatigue.enabled:
            return None
        result = fatigue_reader.read(grab(), save_debug=True)
        if not result.ok:
            logger.warning("未能识别疲劳值 OCR 文本: %r", result.raw_text)
            return None
        ctx.last_fatigue = result.current
        logger.info(
            "疲劳值: %s/%s",
            result.current,
            result.max_value if result.max_value is not None else "?",
        )
        if result.current is not None and result.current <= config.fatigue.stop_at:
            logger.info("疲劳值已为 %s，停止运行", result.current)
            return "stop"
        return None

    def wait_and_tap(template_key: str) -> bool:
        if not has_template(template_key):
            logger.warning("模板未准备: %s", template_path(template_key).name)
            return False
        name = template_path(template_key).name
        try:
            result = matcher.wait_for(
                grab,
                name,
                timeout=config.wait_timeout,
                poll_interval=config.poll_interval,
            )
        except TimeoutError:
            return False
        tap_match(result)
        return True

    def reset_failures() -> None:
        ctx.failures = 0

    def mark_failure(state: str) -> str | None:
        ctx.failures += 1
        logger.warning("状态 %s 未识别 (%s/%s)", state, ctx.failures, ctx.max_failures)
        if ctx.failures >= ctx.max_failures:
            logger.error("连续失败次数过多，停止运行")
            return None
        time.sleep(config.poll_interval)
        return state

    def is_main_city(screen) -> bool:
        if find_template(screen, "main_city"):
            return True
        fatigue = fatigue_reader.read(screen)
        if fatigue.ok and not find_template(screen, "dungeon_select"):
            if find_template(screen, "in_dungeon"):
                return False
            return True
        return False

    def tap_template_or_ratio(
        template_key: str,
        fallback: tuple[float, float],
        label: str,
        *,
        alt_keys: tuple[str, ...] = (),
    ) -> bool:
        battle_prepare()
        for key in (template_key, *alt_keys):
            screen = grab()
            result = find_template(screen, key)
            if result:
                logger.info("点击 %s（模板 %s）", label, template_path(key).name)
                tap_match(result)
                return True
        if not any(has_template(k) for k in (template_key, *alt_keys)):
            logger.info("点击 %s（坐标 %s）", label, fallback)
            tap_ratio(*fallback)
            return True
        return False

    def is_dungeon_select(screen) -> bool:
        return find_template(screen, "dungeon_select") is not None

    def is_dungeon_detail(screen) -> bool:
        return find_template(screen, "dungeon_detail") is not None

    def nudge_character() -> None:
        """轻微移动角色。"""
        battle_prepare()
        if dungeon.nudge_method == "key":
            interval = dungeon.nudge_interval
            for direction in ("up", "down", "left", "right"):
                input_ctrl.press_key(direction, times=1, interval=interval, delay=False)
                time.sleep(interval)
            logger.info("已完成方向键微移")
            return

        screen = grab()
        cx, cy = dungeon.nudge_center
        delta = dungeon.nudge_delta
        swipes = [
            (cx, cy, cx, cy - delta),
            (cx, cy, cx, cy + delta),
            (cx, cy, cx - delta, cy),
            (cx, cy, cx + delta, cy),
        ]
        for x1, y1, x2, y2 in swipes:
            input_ctrl.swipe_ratio(
                screen,
                x1,
                y1,
                x2,
                y2,
                duration_ms=180,
                delay=False,
                mapper=mapper,
            )
            time.sleep(dungeon.nudge_interval)
        logger.info("已完成轮盘短滑动微移")

    def on_scan() -> str | None:
        ctx.last_state = "scan"
        stop = check_fatigue()
        if stop:
            return stop

        screen = grab()
        if find_template(screen, "settlement"):
            reset_failures()
            return "settlement"
        if is_dungeon_detail(screen):
            reset_failures()
            return "dungeon_detail"
        if is_dungeon_select(screen):
            reset_failures()
            ctx.moved_right = True
            return "dungeon_select"
        if is_main_city(screen):
            reset_failures()
            ctx.moved_right = False
            ctx.dungeon_step = 0
            return "main_city"

        logger.info("未识别当前界面，默认从主城流程开始")
        reset_failures()
        return "main_city"

    def on_main_city() -> str | None:
        ctx.last_state = "main_city"
        stop = check_fatigue()
        if stop:
            return stop

        screen = grab()
        capture.focus_window()
        method = config.movement.method.lower()

        if method in ("swipe", "both"):
            logger.info(
                "向右滑动 %s 次: %s -> %s",
                config.movement.swipe_times,
                config.movement.swipe_from,
                config.movement.swipe_to,
            )
            for _ in range(config.movement.swipe_times):
                input_ctrl.swipe_ratio(
                    screen,
                    *config.movement.swipe_from,
                    *config.movement.swipe_to,
                    duration_ms=350,
                    delay=False,
                    mapper=mapper,
                )
                time.sleep(config.movement.press_interval)

        if method in ("key", "both"):
            logger.info("方向键向右 x%s", config.movement.right_presses)
            input_ctrl.press_right(
                times=config.movement.right_presses,
                interval=config.movement.press_interval,
                delay=False,
            )

        time.sleep(config.movement.after_move_wait)
        ctx.moved_right = True
        reset_failures()
        return "dungeon_select"

    def on_dungeon_select() -> str | None:
        ctx.last_state = "dungeon_select"
        if not is_dungeon_select(grab()):
            if is_main_city(grab()):
                ctx.moved_right = False
                return "main_city"
            if has_template("dungeon_select"):
                try:
                    matcher.wait_for(
                        grab,
                        template_path("dungeon_select").name,
                        timeout=config.wait_timeout,
                        poll_interval=config.poll_interval,
                    )
                except TimeoutError:
                    return mark_failure("dungeon_select")

        result = find_template(grab(), "blocked_trial")
        if result:
            logger.info("点击「封锁的试验场」")
            tap_match(result)
            reset_failures()
            time.sleep(config.action_delay)
            return "dungeon_detail"

        if not has_template("blocked_trial"):
            tap_ratio(*dungeon.tap("blocked_trial"))
            reset_failures()
            time.sleep(config.action_delay)
            return "dungeon_detail"

        return mark_failure("dungeon_select")

    def on_dungeon_detail() -> str | None:
        ctx.last_state = "dungeon_detail"
        stop = check_fatigue()
        if stop:
            return stop
        if has_template("dungeon_detail"):
            try:
                matcher.wait_for(
                    grab,
                    template_path("dungeon_detail").name,
                    timeout=config.wait_timeout,
                    poll_interval=config.poll_interval,
                )
            except TimeoutError:
                return mark_failure("dungeon_detail")
        if not tap_template_or_ratio("map_first", dungeon.tap("map_first"), "第一个地图"):
            return mark_failure("dungeon_detail")
        time.sleep(config.action_delay)
        if not tap_template_or_ratio("start_battle", dungeon.tap("start_battle"), "战斗开始"):
            return mark_failure("dungeon_detail")
        ctx.dungeon_step = 0
        reset_failures()
        return "in_battle"

    def on_in_battle() -> str | None:
        ctx.last_state = "in_battle"
        step = ctx.dungeon_step
        if step == 0:
            battle_prepare()
            screen = wait_battle_ready(grab, dungeon)
            cast_skill_w(
                input_ctrl,
                dungeon,
                screen,
                mapper=mapper,
                capture=capture,
            )
            time.sleep(dungeon.after_skill_wait)
            ctx.dungeon_step += 1
            return "in_battle"
        if step == 1:
            if not tap_template_or_ratio(
                "settings_gear", dungeon.tap("settings_gear"), "设置齿轮"
            ):
                return mark_failure("in_battle")
            time.sleep(config.action_delay)
            battle_pause()
            ctx.dungeon_step += 1
            return "in_battle"
        if step == 2:
            if not tap_template_or_ratio("unstuck", dungeon.tap("unstuck"), "脱离卡死"):
                return mark_failure("in_battle")
            time.sleep(config.action_delay)
            battle_pause()
            ctx.dungeon_step += 1
            return "in_battle"
        if step == 3:
            time.sleep(dungeon.unstuck_wait)
            ctx.dungeon_step += 1
            return "in_battle"
        if step == 4:
            if not tap_template_or_ratio(
                "settings_close", dungeon.tap("settings_close"), "关闭弹窗叉号"
            ):
                return mark_failure("in_battle")
            time.sleep(config.action_delay)
            battle_pause()
            ctx.dungeon_step += 1
            return "in_battle"
        if step == 5:
            nudge_character()
            time.sleep(config.action_delay)
            battle_pause()
            ctx.dungeon_step += 1
            return "in_battle"
        if step == 6:
            if not tap_template_or_ratio(
                "settings_gear", dungeon.tap("settings_gear"), "设置齿轮"
            ):
                return mark_failure("in_battle")
            time.sleep(config.action_delay)
            battle_pause()
            ctx.dungeon_step += 1
            return "in_battle"
        if step == 7:
            if not tap_template_or_ratio(
                "return_town", dungeon.tap("return_town"), "返回城镇"
            ):
                return mark_failure("in_battle")
            time.sleep(config.action_delay)
            battle_pause()
            ctx.dungeon_step += 1
            return "in_battle"
        if step == 8:
            if not tap_template_or_ratio(
                "confirm_leave",
                dungeon.tap("confirm_leave"),
                "确认离开地下城",
                alt_keys=("confirm",),
            ):
                return mark_failure("in_battle")
            ctx.rounds += 1
            ctx.dungeon_step = 0
            reset_failures()
            logger.info("第 %s 轮完成，已返回城镇", ctx.rounds)
            if ctx.max_rounds > 0 and ctx.rounds >= ctx.max_rounds:
                return None
            time.sleep(config.action_delay)
            return "scan"
        ctx.dungeon_step = 0
        return mark_failure("in_battle")

    def on_settlement() -> str | None:
        ctx.last_state = "settlement"
        if wait_and_tap("confirm"):
            ctx.rounds += 1
            reset_failures()
            if ctx.max_rounds > 0 and ctx.rounds >= ctx.max_rounds:
                return None
            return "scan"
        return mark_failure("settlement")

    def on_stop() -> str | None:
        logger.info("疲劳耗尽或触发停止条件，结束运行")
        return None

    sm = StateMachine()
    sm.register("scan", on_scan)
    sm.register("main_city", on_main_city)
    sm.register("dungeon_select", on_dungeon_select)
    sm.register("dungeon_detail", on_dungeon_detail)
    sm.register("in_battle", on_in_battle)
    sm.register("settlement", on_settlement)
    sm.register("stop", on_stop)
    return sm
