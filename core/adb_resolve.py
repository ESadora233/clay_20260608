"""查找本机 adb 可执行文件。"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# 常见安装位置（含应用宝/Android SDK/项目内置）
COMMON_ADB_CANDIDATES: list[Path] = [
    PROJECT_ROOT / "tools" / "platform-tools" / "adb.exe",
    PROJECT_ROOT / "tools" / "platform-tools" / "adb",
    Path(os.environ.get("LOCALAPPDATA", "")) / "Android" / "Sdk" / "platform-tools" / "adb.exe",
    Path(os.environ.get("ANDROID_HOME", "")) / "platform-tools" / "adb.exe",
    Path(os.environ.get("ANDROID_SDK_ROOT", "")) / "platform-tools" / "adb.exe",
    Path(r"C:\Android\platform-tools\adb.exe"),
    Path(r"D:\Android\platform-tools\adb.exe"),
    Path(r"C:\Program Files\Tencent\Androws\adb.exe"),
    Path(os.environ.get("LOCALAPPDATA", "")) / "Tencent" / "Androws" / "adb.exe",
]


def resolve_adb_executable(configured: str = "") -> str:
    """
    解析 adb 路径，优先级:
    1. config.yaml 中的 adb.executable
    2. 系统 PATH
    3. 常见安装目录
    """
    if configured.strip():
        path = Path(configured.strip()).expanduser()
        if path.is_file():
            return str(path.resolve())
        raise FileNotFoundError(f"配置的 adb 路径不存在: {path}")

    from_path = shutil.which("adb")
    if from_path:
        return from_path

    for candidate in COMMON_ADB_CANDIDATES:
        if candidate.is_file():
            return str(candidate.resolve())

    searched = "\n".join(f"  - {p}" for p in COMMON_ADB_CANDIDATES)
    raise FileNotFoundError(
        "未找到 adb。请任选一种方式:\n"
        "1. 运行: powershell -ExecutionPolicy Bypass -File scripts/setup_adb.ps1\n"
        "2. 下载 Android Platform Tools 并加入 PATH\n"
        "   https://developer.android.com/tools/releases/platform-tools\n"
        "3. 在 config.yaml 设置 adb.executable 为 adb.exe 完整路径\n"
        f"已自动查找位置:\n{searched}"
    )
