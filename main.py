"""
应用宝 + ADB 自动化框架入口。

用法:
  python main.py connect          # 连接模拟器
  python main.py screenshot       # 保存当前截图
  python main.py match <模板名>   # 测试模板匹配
  python main.py demo             # 运行示例状态机
  python main.py doctor           # 环境诊断
  python main.py crop <图> <名>   # 裁切模板
  python main.py run [farm]       # 运行自动化流程
  python main.py fatigue          # 读取疲劳值
  python main.py key right          # 测试方向右键
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path

from core.adb import AdbClient, AdbError
from core.adb_resolve import resolve_adb_executable
from core.capture import CaptureError, ScreenCapture
from core.config import load_config
from core.crop_tool import crop_image, parse_region
from core.fatigue import FatigueConfig, FatigueReader
from core.input import InputController
from core.matcher import TemplateMatcher
from core.state_machine import StateMachine
from flows.registry import get_flow_builder


def setup_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )


def build_context(config_path: str):
    config = load_config(config_path)
    adb = AdbClient(config.adb)
    capture = ScreenCapture(
        adb,
        temp_dir=config.temp_dir,
        mode=config.capture.mode,
        window_titles=list(config.capture.window_titles),
        window_rect=config.capture.window_rect,
        client_offset=config.capture.client_offset,
        blank_threshold=config.capture.blank_threshold,
        adb_fallback_to_window=config.capture.adb_fallback_to_window,
    )
    matcher = TemplateMatcher(config.templates_dir, config.threshold)
    input_ctrl = InputController(
        adb,
        config.action_delay,
        capture=capture,
        input_mode=config.input.mode,
        pc_method=config.input.pc_method,
    )
    return config, adb, capture, matcher, input_ctrl


def cmd_connect(args: argparse.Namespace) -> None:
    _, adb, _, _, _ = build_context(args.config)
    adb.connect()
    print(f"已连接设备: {adb.serial}")


def cmd_screenshot(args: argparse.Namespace) -> None:
    config, _, capture, _, _ = build_context(args.config)
    screen = capture.grab(save_debug=True)
    out = Path(config.temp_dir) / "manual.png"
    import cv2

    cv2.imwrite(str(out), screen)
    print(f"截图已保存: {out} ({screen.shape[1]}x{screen.shape[0]})")


def cmd_match(args: argparse.Namespace) -> None:
    config, _, capture, matcher, input_ctrl = build_context(args.config)
    screen = capture.grab(save_debug=True)
    result = matcher.find(screen, args.template)

    if not result:
        print(f"未匹配到模板: {args.template} (threshold={config.threshold})")
        sys.exit(1)

    print(
        f"匹配成功: {result.name}\n"
        f"  confidence: {result.confidence:.3f}\n"
        f"  center: {result.center}\n"
        f"  region: {result.top_left} -> {result.bottom_right}"
    )

    if args.tap:
        input_ctrl.tap(*result.center)


def cmd_doctor(args: argparse.Namespace) -> None:
    config = load_config(args.config)
    ok = True

    print("=== 环境诊断 ===")

    try:
        adb_path = resolve_adb_executable(config.adb.executable)
        print(f"[OK] adb: {adb_path}")
    except FileNotFoundError as exc:
        ok = False
        print(f"[FAIL] adb 未找到\n{exc}")

    templates = list(Path(config.templates_dir).glob("*.png"))
    if templates:
        print(f"[OK] 模板: {len(templates)} 个 ({config.templates_dir})")
    else:
        print(f"[WARN] 模板目录为空: {config.templates_dir}")

    print(f"[INFO] 连接地址: {config.adb.host}:{config.adb.port}")

    if not ok:
        print("\n请先安装 adb，然后执行: python main.py connect")
        sys.exit(1)

    try:
        adb = AdbClient(config.adb)
        all_devices = adb.list_devices_with_status()
        for serial, status in all_devices:
            tag = "OK" if status == "device" else "WARN"
            print(f"[{tag}] {serial}\t{status}")
            if serial.endswith(":5037"):
                print("       ↑ 5037 是 adb 服务端口，误连会显示 offline，将自动 disconnect")

        adb.connect()
        print(f"[OK] 当前使用设备: {adb.serial}")
        _, _, capture, _, input_ctrl = build_context(args.config)
        screen = capture.grab()
        print(f"[OK] 截图成功: {screen.shape[1]}x{screen.shape[0]} (mean={screen.mean():.1f})")
        if capture.target:
            print(
                f"[OK] 输入目标: {capture.target.title} "
                f"({capture.target.width}x{capture.target.height}) "
                f"class={capture.target.class_name} hwnd={capture.target.hwnd}"
            )
        if capture._device_w and capture._device_h:
            print(f"[OK] ADB 触控坐标系: {capture._device_w}x{capture._device_h}")
        print(f"[INFO] 截图模式: {config.capture.mode}")
        emu = config.input.emulator_mode
        preset = MODE_PRESETS.get(emu.strip().lower())
        if preset:
            print(f"[INFO] 模拟器模式: {emu} — {preset.description}")
            print(
                f"[INFO] 移动={config.movement.method}，"
                f"技能={config.dungeon.skill_method}，"
                f"微移={config.dungeon.nudge_method}"
            )
        else:
            print(f"[INFO] 模拟器模式: {emu}（custom，使用手动配置）")
        if input_ctrl._use_pc_input() or input_ctrl._mode_hybrid():
            mode = "hybrid" if input_ctrl._mode_hybrid() else "PC 窗口"
            print(f"[INFO] 输入模式: {mode}（点击/滑动/按键双通道）")
        else:
            print("[INFO] 输入模式: ADB")
    except CaptureError as exc:
        print(f"[FAIL] 截图: {exc}")
        sys.exit(1)
    except AdbError as exc:
        print(f"[FAIL] ADB 连接: {exc}")
        sys.exit(1)

    print("\n环境正常，可以运行 screenshot / match。")


def _resolve_template_name(name: str) -> str:
    return name if name.lower().endswith(".png") else f"{name}.png"


def _resolve_crop_source(config, source: str | None) -> Path:
    if source:
        path = Path(source)
        if path.is_file():
            return path
        alt = Path(config.temp_dir) / source
        if alt.is_file():
            return alt
        print(f"文件不存在: {source}")
        sys.exit(1)

    default = Path(config.temp_dir) / "manual.png"
    if default.is_file():
        return default
    print("未指定截图，请先运行: python main.py screenshot")
    print("或: python main.py crop <模板名> --live")
    sys.exit(1)


from core.config_store import update_capture_window, update_dungeon_tap, update_skill_w_ratio
from core.emulator_mode import MODE_PRESETS
from core.pick_point import pick_point_ratio
from core.ui_points import PICK_POINT_LABELS, resolve_pick_name
from core.window_capture import list_visible_windows


def cmd_windows(args: argparse.Namespace) -> None:
    print("=== 可见窗口（可用于 capture.window_titles / window_rect）===")
    print("格式: [left, top, width, height]  标题\n")
    for idx, (left, top, width, height, title) in enumerate(list_visible_windows(), start=1):
        print(f"{idx:2d}. [{left}, {top}, {width}, {height}]  {title}")
    print("\n选择窗口: python main.py pick-window")


def cmd_pick_window(args: argparse.Namespace) -> None:
    windows = list_visible_windows()
    if not windows:
        print("未找到可用窗口")
        sys.exit(1)

    print("=== 选择截图窗口 ===")
    for idx, (left, top, width, height, title) in enumerate(windows, start=1):
        print(f"{idx:2d}. [{left}, {top}, {width}, {height}]  {title}")

    if args.index is not None:
        choice = args.index
    else:
        try:
            raw = input("\n输入序号并回车: ").strip()
            choice = int(raw)
        except (ValueError, EOFError):
            print("已取消")
            sys.exit(1)

    if choice < 1 or choice > len(windows):
        print("序号无效")
        sys.exit(1)

    left, top, width, height, title = windows[choice - 1]
    update_capture_window(args.config, (left, top, width, height), title)
    print(f"已写入 {args.config}:")
    print(f"  capture.window_rect: [{left}, {top}, {width}, {height}]")
    print("提示: 若输入仍无效，不要用手动 rect，清空 window_rect: [] 让程序自动找 Androws 子窗口")


def cmd_crop(args: argparse.Namespace) -> None:
    import cv2

    config = load_config(args.config)

    if args.live:
        adb = AdbClient(config.adb)
        adb.connect()
        capture = ScreenCapture(adb, config.temp_dir)
        screen = capture.grab(save_debug=True)
        source = Path(config.temp_dir) / "crop_source.png"
        cv2.imwrite(str(source), screen)
        print(f"已从设备截图: {source}")
    else:
        source = _resolve_crop_source(config, args.source)

    output = Path(config.templates_dir) / _resolve_template_name(args.name)
    region = parse_region(args.region) if args.region else None

    try:
        saved = crop_image(source, output, region=region)
    except SystemExit:
        raise
    except Exception as exc:
        print(f"裁切失败: {exc}")
        sys.exit(1)

    print(f"模板已保存: {saved}")
    print(f"验证: python main.py match {saved.name}")


def cmd_fatigue(args: argparse.Namespace) -> None:
    import cv2

    config = load_config(args.config)
    _, adb, capture, _, _ = build_context(args.config)
    adb.connect()

    screen = capture.grab(save_debug=True)
    reader = FatigueReader(
        FatigueConfig(
            enabled=True,
            stop_at=config.fatigue.stop_at,
            region=config.fatigue.region,
        ),
        debug_dir=config.temp_dir,
    )
    crop = reader.crop_region(screen)
    crop_path = Path(config.temp_dir) / "fatigue_crop.png"
    cv2.imwrite(str(crop_path), crop)

    result = reader.read(screen, save_debug=False)
    print(f"OCR 原文: {result.raw_text!r}")
    print(f"裁剪区域: {crop_path} ({crop.shape[1]}x{crop.shape[0]})")
    print(f"配置 region: {config.fatigue.region}")

    if not result.ok:
        print("未能解析疲劳值，请调整 config.yaml 的 fatigue.region")
        print("可用: python main.py crop fatigue_roi --region ... 重新标定")
        sys.exit(1)

    print(f"疲劳值: {result.current}/{result.max_value}")
    if result.should_stop:
        print(f"疲劳 <= {config.fatigue.stop_at}，流程将停止")
    else:
        print("疲劳充足，可继续搬砖")


def cmd_key(args: argparse.Namespace) -> None:
    _, adb, _, _, input_ctrl = build_context(args.config)
    adb.connect()
    input_ctrl.press_key(
        args.direction,
        times=args.times,
        interval=args.interval,
    )
    print(f"已发送按键: {args.direction} x{args.times}")


def cmd_probe_input(args: argparse.Namespace) -> None:
    """在截图上标出即将点击的屏幕坐标，用于排查坐标偏移。"""
    import cv2

    config, _, capture, _, _ = build_context(args.config)
    screen = capture.grab(save_debug=True)
    target = capture.target
    h, w = screen.shape[:2]
    overlay = screen.copy()

    points: list[tuple[str, int, int]] = [
        ("center", w // 2, h // 2),
        (
            "swipe_from",
            int(config.movement.swipe_from[0] * w),
            int(config.movement.swipe_from[1] * h),
        ),
        (
            "swipe_to",
            int(config.movement.swipe_to[0] * w),
            int(config.movement.swipe_to[1] * h),
        ),
        (
            "skill_w",
            int(config.dungeon.skill_w_ratio[0] * w),
            int(config.dungeon.skill_w_ratio[1] * h),
        ),
    ]

    if target:
        print(f"目标: {target.title} hwnd={target.hwnd} rect={target.rect}")
    print(f"截图: {w}x{h}")

    for name, x, y in points:
        sx, sy = capture.to_screen_coords(x, y)
        cv2.circle(overlay, (x, y), 24, (0, 0, 255), 3)
        cv2.putText(overlay, name, (x + 8, y - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
        print(f"  {name}: 截图({x},{y}) -> 屏幕({sx},{sy})")

    out = Path(config.temp_dir) / "probe_input.png"
    cv2.imwrite(str(out), overlay)
    print(f"已保存: {out}")


def cmd_test_input(args: argparse.Namespace) -> None:
    """测试滑动/点击/按键是否生效。"""
    config, adb, capture, _, input_ctrl = build_context(args.config)
    adb.connect()
    emu = config.input.emulator_mode
    print(f"设备: {adb.serial}，模拟器模式: {emu}，输入: {config.input.mode}")
    print("请把游戏窗口放在前台，5 秒后开始…")
    time.sleep(5)

    screen = capture.grab()
    target = capture.target
    if target:
        print(f"目标窗口: {target.title} hwnd={target.hwnd} rect={target.rect}")
    h, w = screen.shape[:2]
    print(f"截图: {w}x{h}")

    if config.movement.method in ("swipe", "both"):
        print("1) 向右滑动（轮盘移动）")
        input_ctrl.swipe_ratio(
            screen,
            *config.movement.swipe_from,
            *config.movement.swipe_to,
        )
        time.sleep(1)

    if config.movement.method in ("key", "both"):
        print("1) 方向键向右 x3")
        input_ctrl.press_right(times=3, interval=0.15, delay=False)
        time.sleep(1)

    cx, cy = w // 2, h // 2
    print(f"2) 点击屏幕中心 ({cx},{cy})")
    input_ctrl.tap(cx, cy)
    time.sleep(1)

    if config.dungeon.skill_method in ("tap", "both") and config.dungeon.use_skill_tap:
        from core.skill_cast import cast_skill_w, skill_w_ratio

        rx, ry = skill_w_ratio(config.dungeon)
        print(f"3) 点击 W 技能 ({rx:.4f},{ry:.4f})")
        cast_skill_w(input_ctrl, config.dungeon, screen, capture=capture)
    elif config.dungeon.use_skill_key:
        print("3) 按 W 键")
        input_ctrl.press_key("w")
    else:
        print("3) 跳过技能测试（当前模式未启用）")

    print("测试完成 — 切换模式请改 config.yaml 的 input.emulator_mode")


def cmd_test_skill(args: argparse.Namespace) -> None:
    """在战斗中测试 W 技能：连点 + 按键。"""
    import cv2

    from core.battle_ready import is_battle_ui_ready, wait_battle_ready
    from core.skill_cast import cast_skill_w, skill_w_ratio

    config, adb, capture, _, input_ctrl = build_context(args.config)
    adb.connect()
    print("请进本并点「战斗开始」，脚本将自动等待加载完成再放 W…")
    print("（不要手动切走，保持游戏窗口可见）")
    time.sleep(2)

    screen = wait_battle_ready(capture.grab, config.dungeon)
    ready = is_battle_ui_ready(screen, config.dungeon)
    print(f"战斗就绪检测: {'通过' if ready else '超时/未完全就绪'}")
    h, w = screen.shape[:2]
    rx, ry = skill_w_ratio(config.dungeon)
    sx, sy = int(rx * w), int(ry * h)
    dx, dy = capture.map_to_device(sx, sy)
    print(f"W 目标: ratio=({rx:.4f},{ry:.4f}) 截图=({sx},{sy}) ADB=({dx},{dy})")
    print(f"方式: {config.dungeon.skill_method} 连点={config.dungeon.skill_tap_times} 次")

    overlay = screen.copy()
    cv2.circle(overlay, (sx, sy), 22, (0, 0, 255), 3)
    cv2.putText(overlay, "W", (sx + 8, sy - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 255), 2)
    out = Path(config.temp_dir) / "test_skill_target.png"
    cv2.imwrite(str(out), overlay)
    print(f"目标标记图: {out}")

    cast_skill_w(input_ctrl, config.dungeon, screen, capture=capture)
    print("已发送，观察是否释放 W 技能")


def cmd_pick_point(args: argparse.Namespace) -> None:
    """标定 UI 点击位置并写入 config.yaml。"""
    import cv2

    try:
        tap_name = resolve_pick_name(args.name)
    except ValueError as exc:
        print(exc)
        sys.exit(1)

    label = PICK_POINT_LABELS.get(tap_name, tap_name)
    if tap_name == "settings_gear":
        print("提示: 点顶部状态栏的小齿轮，不要点右侧迷你地图")
    config, adb, capture, _, input_ctrl = build_context(args.config)
    adb.connect()
    print(f"标定: {label} ({tap_name})")
    print("请打开对应界面，5 秒后截图…")
    time.sleep(5)

    screen = capture.grab(save_debug=True)
    source = Path(config.temp_dir) / f"pick_{tap_name}.png"
    cv2.imwrite(str(source), screen)
    print(f"截图: {source}")

    rx, ry = pick_point_ratio(screen, window_title=f"pick-point - {label}")
    if tap_name == "skill_w":
        update_skill_w_ratio(args.config, (rx, ry))
        print(f"已写入 dungeon.skill_w_ratio: [{rx:.4f}, {ry:.4f}]")
    else:
        update_dungeon_tap(args.config, tap_name, (rx, ry))
        print(f"已写入 dungeon.taps.{tap_name}: [{rx:.4f}, {ry:.4f}]")

    if args.test:
        print("3 秒后测试点击…")
        time.sleep(3)
        screen = capture.grab()
        capture.focus_window()
        if tap_name == "skill_w":
            from core.skill_cast import cast_skill_w

            cast_skill_w(input_ctrl, config.dungeon, screen, capture=capture)
        else:
            input_ctrl.tap_ratio(screen, rx, ry)
        print("已发送点击")


def cmd_probe_farm(args: argparse.Namespace) -> None:
    """在截图上标出搬砖流程所有 UI 坐标。"""
    import cv2

    from core.skill_cast import skill_w_ratio

    config, _, capture, _, _ = build_context(args.config)
    screen = capture.grab(save_debug=True)
    h, w = screen.shape[:2]
    overlay = screen.copy()
    dungeon = config.dungeon

    points: list[tuple[str, float, float]] = [
        ("W", *skill_w_ratio(dungeon)),
        ("gear", *dungeon.tap("settings_gear")),
        ("unstuck", *dungeon.tap("unstuck")),
        ("close", *dungeon.tap("settings_close")),
        ("return", *dungeon.tap("return_town")),
        ("confirm", *dungeon.tap("confirm_leave")),
    ]

    for name, rx, ry in points:
        x, y = int(rx * w), int(ry * h)
        cv2.circle(overlay, (x, y), 18, (0, 0, 255), 2)
        cv2.putText(overlay, name, (x + 6, y - 6), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
        print(f"  {name}: ({rx:.4f}, {ry:.4f}) -> ({x}, {y})")

    out = Path(config.temp_dir) / "probe_farm.png"
    cv2.imwrite(str(out), overlay)
    print(f"已保存: {out}")


def cmd_pick_skill(args: argparse.Namespace) -> None:
    """在战斗截图上点击 W 技能按钮，写入 dungeon.skill_w_ratio。"""
    import cv2

    config, adb, capture, _, input_ctrl = build_context(args.config)
    adb.connect()
    print("请进入副本/战斗，确保右下角技能栏可见，5 秒后截图…")
    time.sleep(5)

    screen = capture.grab(save_debug=True)
    source = Path(config.temp_dir) / "pick_skill_source.png"
    cv2.imwrite(str(source), screen)
    print(f"截图: {source} ({screen.shape[1]}x{screen.shape[0]})")

    rx, ry = pick_point_ratio(screen, window_title="pick-skill - 点击 W 技能")
    update_skill_w_ratio(args.config, (rx, ry))
    print(f"已写入 {args.config}: dungeon.skill_w_ratio: [{rx:.4f}, {ry:.4f}]")

    if args.test:
        print("3 秒后测试释放 W…")
        time.sleep(3)
        screen = capture.grab()
        from core.skill_cast import cast_skill_w

        cast_skill_w(input_ctrl, config.dungeon, screen, capture=capture)
        print("已发送，观察是否释放 W 技能")


def cmd_run(args: argparse.Namespace) -> None:
    config, adb, capture, matcher, input_ctrl = build_context(args.config)
    adb.connect()
    logger = logging.getLogger(__name__)
    logger.info("使用设备: %s", adb.serial)

    try:
        builder = get_flow_builder(args.flow)
    except KeyError as exc:
        print(exc)
        sys.exit(1)

    sm = builder(config, capture, matcher, input_ctrl, args.loops)
    start = args.start or ("check" if args.flow == "demo" else "scan")
    print(f"启动流程: {args.flow}，入口状态: {start}，最大轮数: {args.loops or '不限'}")
    sm.run(start=start)


def cmd_demo(args: argparse.Namespace) -> None:
    config, _, capture, matcher, input_ctrl = build_context(args.config)

    def state_check_connection() -> str | None:
        screen = capture.grab(save_debug=True)
        h, w = screen.shape[:2]
        logging.info("当前分辨率: %sx%s", w, h)
        # 示例：若存在模板则点击，否则结束
        templates = list(Path(config.templates_dir).glob("*.png"))
        if not templates:
            logging.warning(
                "assets/templates/ 下没有模板，请将按钮截图保存为 .png 后再运行"
            )
            return None
        name = templates[0].name
        result = matcher.find(screen, name)
        if result:
            input_ctrl.tap(*result.center)
            return "done"
        logging.info("未找到模板 %s，示例结束", name)
        return None

    sm = StateMachine()
    sm.register("check", state_check_connection)
    sm.register("done", lambda: None)
    sm.run(start="check")


def main() -> None:
    parser = argparse.ArgumentParser(description="应用宝 ADB 自动化框架")
    parser.add_argument(
        "-c", "--config",
        default="config.yaml",
        help="配置文件路径",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_connect = sub.add_parser("connect", help="连接应用宝模拟器")
    p_connect.set_defaults(func=cmd_connect)

    p_shot = sub.add_parser("screenshot", help="截取并保存当前屏幕")
    p_shot.set_defaults(func=cmd_screenshot)

    p_match = sub.add_parser("match", help="测试模板匹配")
    p_match.add_argument("template", help="模板文件名，如 start.png")
    p_match.add_argument(
        "--tap",
        action="store_true",
        help="匹配成功后点击中心点",
    )
    p_match.set_defaults(func=cmd_match)

    p_demo = sub.add_parser("demo", help="运行示例状态机")
    p_demo.set_defaults(func=cmd_demo)

    p_doctor = sub.add_parser("doctor", help="检查 adb、设备与截图")
    p_doctor.set_defaults(func=cmd_doctor)

    p_crop = sub.add_parser("crop", help="从截图裁切模板")
    p_crop.add_argument(
        "name",
        help="输出模板名，如 dungeon_entry 或 dungeon_entry.png",
    )
    p_crop.add_argument(
        "source",
        nargs="?",
        default=None,
        help="截图路径（默认 runtime/screenshots/manual.png）",
    )
    p_crop.add_argument(
        "--live",
        action="store_true",
        help="先从设备截图，再框选裁切",
    )
    p_crop.add_argument(
        "--region",
        default=None,
        help="非交互裁切: x,y,width,height",
    )
    p_crop.set_defaults(func=cmd_crop)

    p_windows = sub.add_parser("windows", help="列出 PC 可见窗口")
    p_windows.set_defaults(func=cmd_windows)

    p_pick = sub.add_parser("pick-window", help="交互选择截图窗口并写入 config")
    p_pick.add_argument("--index", type=int, default=None, help="直接指定 windows 列表序号")
    p_pick.set_defaults(func=cmd_pick_window)

    p_run = sub.add_parser("run", help="运行自动化流程")
    p_run.add_argument(
        "flow",
        nargs="?",
        default="farm",
        choices=["farm", "demo"],
        help="流程名称（默认 farm）",
    )
    p_run.add_argument(
        "--loops",
        type=int,
        default=0,
        help="最大循环轮数，0 表示不限制",
    )
    p_run.add_argument(
        "--start",
        default=None,
        help="起始状态名（默认 farm=scan, demo=check）",
    )
    p_run.set_defaults(func=cmd_run)

    p_fatigue = sub.add_parser("fatigue", help="读取左上角疲劳值")
    p_fatigue.set_defaults(func=cmd_fatigue)

    p_key = sub.add_parser("key", help="发送方向键/按键（adb keyevent）")
    p_key.add_argument(
        "direction",
        choices=["up", "down", "left", "right", "w", "enter", "space", "back"],
        help="按键名称",
    )
    p_key.add_argument(
        "--times",
        type=int,
        default=1,
        help="连按次数",
    )
    p_key.add_argument(
        "--interval",
        type=float,
        default=None,
        help="连按间隔（秒），默认用 config action_delay",
    )
    p_key.set_defaults(func=cmd_key)

    p_probe = sub.add_parser("probe-input", help="标出点击坐标到截图上，排查偏移")
    p_probe.set_defaults(func=cmd_probe_input)

    p_pick_skill = sub.add_parser("pick-skill", help="点击标定 W 技能位置并写入 config")
    p_pick_skill.add_argument("--test", action="store_true", help="标定后立即测试释放 W")
    p_pick_skill.set_defaults(func=cmd_pick_skill)

    p_pick_point = sub.add_parser("pick-point", help="标定 UI 坐标（gear/unstuck/close 等）")
    p_pick_point.add_argument(
        "name",
        help="gear, unstuck, close, return, confirm, w, blocked_trial, map_first, start_battle",
    )
    p_pick_point.add_argument("--test", action="store_true", help="标定后立即测试点击")
    p_pick_point.set_defaults(func=cmd_pick_point)

    p_probe_farm = sub.add_parser("probe-farm", help="标出战斗流程所有 UI 坐标")
    p_probe_farm.set_defaults(func=cmd_probe_farm)

    p_test_skill = sub.add_parser("test-skill", help="在战斗中测试 W 技能（连点+按键）")
    p_test_skill.set_defaults(func=cmd_test_skill)

    p_test = sub.add_parser("test-input", help="测试滑动/点击/按键是否生效")
    p_test.set_defaults(func=cmd_test_input)

    args = parser.parse_args()
    config = load_config(args.config)
    setup_logging(config.log_level)
    args.func(args)


if __name__ == "__main__":
    main()
