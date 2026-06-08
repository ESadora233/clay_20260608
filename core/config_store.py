"""读写 config.yaml 中的 capture 窗口配置。"""

from __future__ import annotations

from pathlib import Path

import yaml


def update_capture_window(
    config_path: str | Path,
    window_rect: tuple[int, int, int, int],
    window_title: str = "",
) -> None:
    path = Path(config_path)
    with path.open("r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}

    capture = raw.setdefault("capture", {})
    capture["mode"] = "window"
    capture["window_rect"] = [int(window_rect[0]), int(window_rect[1]), int(window_rect[2]), int(window_rect[3])]

    if window_title.strip():
        titles = list(capture.get("window_titles") or [])
        if window_title not in titles:
            titles.insert(0, window_title)
        capture["window_titles"] = titles[:5]

    with path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(raw, f, allow_unicode=True, sort_keys=False)


def update_dungeon_tap(
    config_path: str | Path,
    name: str,
    ratio: tuple[float, float],
) -> None:
    path = Path(config_path)
    with path.open("r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}

    dungeon = raw.setdefault("dungeon", {})
    taps = dungeon.setdefault("taps", {})
    taps[name] = [round(ratio[0], 4), round(ratio[1], 4)]

    with path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(raw, f, allow_unicode=True, sort_keys=False)


def update_skill_w_ratio(
    config_path: str | Path,
    ratio: tuple[float, float],
) -> None:
    path = Path(config_path)
    with path.open("r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}

    dungeon = raw.setdefault("dungeon", {})
    dungeon["use_skill_tap"] = True
    dungeon["skill_w_ratio"] = [round(ratio[0], 4), round(ratio[1], 4)]

    with path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(raw, f, allow_unicode=True, sort_keys=False)
