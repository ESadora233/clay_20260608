"""配置加载。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

from core.adb import AdbConfig
from core.emulator_mode import apply_emulator_mode


@dataclass
class CaptureSettings:
    mode: str = "window"
    window_titles: tuple[str, ...] = ("应用宝", "Androws", "腾讯")
    window_rect: tuple[int, int, int, int] | None = None
    client_offset: tuple[int, int] = (0, 0)
    blank_threshold: float = 1.0
    adb_fallback_to_window: bool = True


@dataclass
class InputSettings:
    # hybrid=PC+ADB 双发；adb=仅 ADB；window=仅 PC
    mode: str = "hybrid"
    # physical=真实鼠标（应用宝推荐）；postmessage=窗口消息
    pc_method: str = "physical"
    # keyboard=方向键+W键；mouse=轮盘滑动+点击技能；custom=完全按下方 movement/dungeon 配置
    emulator_mode: str = "mouse"


@dataclass
class MovementSettings:
    right_presses: int = 5
    press_interval: float = 0.12
    after_move_wait: float = 1.5
    method: str = "swipe"
    swipe_from: tuple[float, float] = (0.15, 0.78)
    swipe_to: tuple[float, float] = (0.45, 0.78)
    swipe_times: int = 2


DEFAULT_DUNGEON_TAPS: dict[str, tuple[float, float]] = {
    "blocked_trial": (0.30, 0.61),
    "map_first": (0.15, 0.38),
    "start_battle": (0.82, 0.88),
    "settings_gear": (0.835, 0.028),
    "unstuck": (0.70, 0.82),
    "settings_close": (0.78, 0.18),
    "return_town": (0.88, 0.82),
    "confirm_leave": (0.58, 0.58),
}


@dataclass
class DungeonSettings:
    after_enter_wait: float = 4.0
    after_skill_wait: float = 1.5
    battle_ready_timeout: float = 30.0
    battle_ready_poll: float = 0.5
    battle_ready_settle: float = 0.8
    battle_step_delay: float = 0.8
    unstuck_wait: float = 7.0
    nudge_interval: float = 0.15
    nudge_method: str = "swipe"
    nudge_center: tuple[float, float] = (0.25, 0.75)
    nudge_delta: float = 0.08
    skill_w_ratio: tuple[float, float] = (0.42, 0.86)
    skill_w_offset: tuple[float, float] = (0.0, -0.02)
    use_skill_tap: bool = True
    use_skill_key: bool = True
    skill_method: str = "both"
    skill_tap_times: int = 2
    skill_tap_interval: float = 0.15
    taps: dict[str, tuple[float, float]] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        merged = dict(DEFAULT_DUNGEON_TAPS)
        if self.taps:
            merged.update(self.taps)
        self.taps = merged

    def tap(self, name: str) -> tuple[float, float]:
        if name not in self.taps:
            raise KeyError(f"未知 UI 坐标: {name}")
        return self.taps[name]


@dataclass
class FatigueSettings:
    enabled: bool = True
    stop_at: int = 0
    region: tuple[float, float, float, float] = (0.08, 0.05, 0.08, 0.10)


@dataclass
class AppConfig:
    adb: AdbConfig
    capture: CaptureSettings
    input: InputSettings
    temp_dir: str
    templates_dir: str
    threshold: float
    action_delay: float
    wait_timeout: float
    poll_interval: float
    log_level: str
    fatigue: FatigueSettings
    movement: MovementSettings
    dungeon: DungeonSettings


def load_config(path: str | Path = "config.yaml") -> AppConfig:
    config_path = Path(path)
    with config_path.open("r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}

    adb_raw = raw.get("adb", {})
    capture_raw = raw.get("capture", {})
    input_raw = raw.get("input", {})
    matcher_raw = raw.get("matcher", {})
    runtime_raw = raw.get("runtime", {})
    logging_raw = raw.get("logging", {})
    fatigue_raw = raw.get("fatigue", {})
    movement_raw = raw.get("movement", {})
    dungeon_raw = raw.get("dungeon", {})

    region_raw = fatigue_raw.get("region", [0.08, 0.05, 0.08, 0.10])
    if len(region_raw) != 4:
        raise ValueError("fatigue.region 必须是 [x, y, width, height] 四个比例值")

    titles_raw = capture_raw.get("window_titles", ["应用宝", "Androws", "腾讯"])
    if isinstance(titles_raw, str):
        titles_raw = [titles_raw]

    rect_raw = capture_raw.get("window_rect")
    window_rect = None
    if rect_raw:
        if len(rect_raw) != 4:
            raise ValueError("capture.window_rect 必须是 [left, top, width, height]")
        window_rect = tuple(int(v) for v in rect_raw)  # type: ignore[assignment]

    offset_raw = capture_raw.get("client_offset", [0, 0])
    if len(offset_raw) != 2:
        raise ValueError("capture.client_offset 必须是 [x, y]")

    taps_raw = dungeon_raw.get("taps") or {}
    dungeon_taps: dict[str, tuple[float, float]] = {}
    for key, value in taps_raw.items():
        if value and len(value) == 2:
            dungeon_taps[str(key)] = (float(value[0]), float(value[1]))

    nudge_center_raw = dungeon_raw.get("nudge_center", [0.25, 0.75])
    if len(nudge_center_raw) != 2:
        raise ValueError("dungeon.nudge_center 必须是 [x, y]")
    client_offset = (int(offset_raw[0]), int(offset_raw[1]))

    input_settings = InputSettings(
        mode=str(input_raw.get("mode", "hybrid")),
        pc_method=str(input_raw.get("pc_method", "physical")),
        emulator_mode=str(input_raw.get("emulator_mode", "mouse")),
    )
    movement_settings = MovementSettings(
        right_presses=int(movement_raw.get("right_presses", 5)),
        press_interval=float(movement_raw.get("press_interval", 0.12)),
        after_move_wait=float(movement_raw.get("after_move_wait", 1.5)),
        method=str(movement_raw.get("method", "swipe")),
        swipe_from=tuple(float(v) for v in movement_raw.get("swipe_from", [0.15, 0.78])),  # type: ignore[assignment]
        swipe_to=tuple(float(v) for v in movement_raw.get("swipe_to", [0.45, 0.78])),  # type: ignore[assignment]
        swipe_times=int(movement_raw.get("swipe_times", 2)),
    )
    dungeon_settings = DungeonSettings(
        after_enter_wait=float(dungeon_raw.get("after_enter_wait", 4.0)),
        after_skill_wait=float(dungeon_raw.get("after_skill_wait", 1.5)),
        battle_ready_timeout=float(dungeon_raw.get("battle_ready_timeout", 30.0)),
        battle_ready_poll=float(dungeon_raw.get("battle_ready_poll", 0.5)),
        battle_ready_settle=float(dungeon_raw.get("battle_ready_settle", 0.8)),
        battle_step_delay=float(dungeon_raw.get("battle_step_delay", 0.8)),
        unstuck_wait=float(dungeon_raw.get("unstuck_wait", 7.0)),
        nudge_interval=float(dungeon_raw.get("nudge_interval", 0.15)),
        nudge_method=str(dungeon_raw.get("nudge_method", "swipe")),
        nudge_center=tuple(float(v) for v in nudge_center_raw),  # type: ignore[assignment]
        nudge_delta=float(dungeon_raw.get("nudge_delta", 0.08)),
        skill_w_ratio=tuple(float(v) for v in dungeon_raw.get("skill_w_ratio", [0.42, 0.86])),  # type: ignore[assignment]
        skill_w_offset=tuple(float(v) for v in dungeon_raw.get("skill_w_offset", [0.0, -0.02])),  # type: ignore[assignment]
        use_skill_tap=bool(dungeon_raw.get("use_skill_tap", True)),
        use_skill_key=bool(dungeon_raw.get("use_skill_key", True)),
        skill_method=str(dungeon_raw.get("skill_method", "both")),
        skill_tap_times=int(dungeon_raw.get("skill_tap_times", 2)),
        skill_tap_interval=float(dungeon_raw.get("skill_tap_interval", 0.15)),
        taps=dungeon_taps,
    )
    apply_emulator_mode(input_settings.emulator_mode, movement_settings, dungeon_settings)

    return AppConfig(
        adb=AdbConfig(
            host=str(adb_raw.get("host", "127.0.0.1")),
            port=int(adb_raw.get("port", 5555)),
            serial=str(adb_raw.get("serial", "")),
            executable=str(adb_raw.get("executable", "")),
        ),
        capture=CaptureSettings(
            mode=str(capture_raw.get("mode", "window")),
            window_titles=tuple(str(t) for t in titles_raw),
            window_rect=window_rect,
            client_offset=client_offset,
            blank_threshold=float(capture_raw.get("blank_threshold", 1.0)),
            adb_fallback_to_window=bool(capture_raw.get("adb_fallback_to_window", True)),
        ),
        input=input_settings,
        temp_dir=str(capture_raw.get("temp_dir", "runtime/screenshots")),
        templates_dir=str(matcher_raw.get("templates_dir", "assets/templates")),
        threshold=float(matcher_raw.get("threshold", 0.85)),
        action_delay=float(runtime_raw.get("action_delay", 0.5)),
        wait_timeout=float(runtime_raw.get("wait_timeout", 10.0)),
        poll_interval=float(runtime_raw.get("poll_interval", 0.5)),
        log_level=str(logging_raw.get("level", "INFO")),
        fatigue=FatigueSettings(
            enabled=bool(fatigue_raw.get("enabled", True)),
            stop_at=int(fatigue_raw.get("stop_at", 0)),
            region=tuple(float(v) for v in region_raw),  # type: ignore[assignment]
        ),
        movement=movement_settings,
        dungeon=dungeon_settings,
    )
