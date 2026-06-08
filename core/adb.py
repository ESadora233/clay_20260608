"""ADB 设备连接与命令封装。"""

from __future__ import annotations

import logging
import subprocess
from dataclasses import dataclass
from typing import Sequence

from core.adb_resolve import resolve_adb_executable

logger = logging.getLogger(__name__)


class AdbError(RuntimeError):
    """ADB 命令执行失败。"""


@dataclass
class AdbConfig:
    host: str = "127.0.0.1"
    port: int = 5555
    serial: str = ""
    executable: str = ""


class AdbClient:
    def __init__(self, config: AdbConfig) -> None:
        self.config = config
        self._serial = config.serial.strip()
        try:
            self._adb = resolve_adb_executable(config.executable)
        except FileNotFoundError as exc:
            raise AdbError(str(exc)) from exc
        logger.debug("使用 adb: %s", self._adb)

    @property
    def serial(self) -> str:
        return self._serial

    def connect(self) -> None:
        """连接应用宝模拟器（无线 ADB）。"""
        self._cleanup_mistaken_server_connection()

        preferred = f"{self.config.host}:{self.config.port}"
        online = self.list_devices()

        if self._serial and self._serial in online:
            logger.info("设备已在线: %s", self._serial)
            return

        if not self._serial and online:
            if preferred in online:
                self._serial = preferred
                logger.info("设备已在线: %s", self._serial)
                return
            if len(online) == 1:
                self._serial = online[0]
                logger.info("已自动选用在线设备: %s", self._serial)
                return

        target = preferred
        result = self._run(["connect", target], check=False, global_cmd=True)
        output = (result.stdout + result.stderr).strip()
        connected = "connected" in output.lower() or "already connected" in output.lower()

        if not connected:
            online = self.list_devices()
            if online:
                logger.warning(
                    "connect %s 失败 (%s)，但检测到已在线设备: %s",
                    target, output, online,
                )
            else:
                raise AdbError(
                    f"无法连接模拟器 {target}: {output}\n"
                    f"提示: 应用宝界面显示的 5037 可能是本机 adb 服务端口；"
                    f"请执行 adb devices 查看实际设备地址（如 127.0.0.1:5555）"
                )

        if not self._serial:
            self._serial = self._pick_device_serial()
        logger.info("使用设备: %s", self._serial)

    def ensure_connected(self) -> None:
        """确保设备在线，必要时自动 connect。"""
        if not self._serial:
            self.connect()
            return

        devices = self.list_devices()
        if self._serial not in devices:
            self.connect()

    def list_devices(self) -> list[str]:
        return [serial for serial, status in self.list_devices_with_status() if status == "device"]

    def list_devices_with_status(self) -> list[tuple[str, str]]:
        result = self._run(["devices"], check=True, global_cmd=True)
        devices: list[tuple[str, str]] = []
        for line in result.stdout.splitlines()[1:]:
            line = line.strip()
            if not line or "\t" not in line:
                continue
            serial, status = line.split("\t", 1)
            devices.append((serial, status))
        return devices

    def _cleanup_mistaken_server_connection(self) -> None:
        """
        断开误连到 adb 服务端口 (5037) 的条目。
        执行 adb connect 127.0.0.1:5037 会出现 offline，应 disconnect。
        """
        for serial, status in self.list_devices_with_status():
            if serial.endswith(":5037") and status == "offline":
                logger.warning("断开误连设备 %s（5037 是 adb 服务端口，不是模拟器）", serial)
                self._run(["disconnect", serial], check=False, global_cmd=True)

    def shell(self, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
        cmd: list[str] = ["shell", *args]
        return self._run(cmd, check=check)

    def exec_out(self, *args: str, check: bool = True) -> bytes:
        """执行 adb exec-out，返回原始二进制（适用于 screencap）。"""
        cmd: list[str] = ["exec-out", *args]
        result = self._run_bytes(cmd, check=check)
        return result.stdout

    def _pick_device_serial(self) -> str:
        devices = self.list_devices()
        if not devices:
            raise AdbError("未发现在线 ADB 设备，请确认应用宝已开启 ADB 调试")

        preferred = f"{self.config.host}:{self.config.port}"
        if preferred in devices:
            return preferred

        host_prefix = f"{self.config.host}:"
        same_host = [d for d in devices if d.startswith(host_prefix)]
        if same_host:
            chosen = same_host[0]
            if len(same_host) > 1:
                logger.warning("同主机多个设备 %s，选用 %s", same_host, chosen)
            else:
                logger.info("选用同主机设备: %s", chosen)
            return chosen

        emulators = [d for d in devices if d.startswith("emulator-")]
        if len(emulators) == 1 and len(devices) == 1:
            return emulators[0]

        if len(devices) == 1:
            return devices[0]

        raise AdbError(
            f"检测到多个设备 {devices}，请在 config.yaml 的 adb.serial 中指定 serial"
        )

    def _run(
        self,
        args: Sequence[str],
        check: bool = True,
        global_cmd: bool = False,
    ) -> subprocess.CompletedProcess[str]:
        cmd = self._build_cmd(args, use_serial=not global_cmd)

        logger.debug("执行: %s", " ".join(cmd))
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=30,
            )
        except FileNotFoundError as exc:
            raise AdbError(f"无法执行 adb: {self._adb}") from exc
        except subprocess.TimeoutExpired as exc:
            raise AdbError(f"ADB 命令超时: {' '.join(cmd)}") from exc

        if check and result.returncode != 0:
            detail = (result.stderr or result.stdout).strip()
            raise AdbError(f"ADB 失败 ({result.returncode}): {detail}")
        return result

    def _run_bytes(
        self,
        args: Sequence[str],
        check: bool = True,
        global_cmd: bool = False,
    ) -> subprocess.CompletedProcess[bytes]:
        cmd = self._build_cmd(args, use_serial=not global_cmd)

        logger.debug("执行: %s", " ".join(cmd))
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                timeout=30,
            )
        except FileNotFoundError as exc:
            raise AdbError(f"无法执行 adb: {self._adb}") from exc
        except subprocess.TimeoutExpired as exc:
            raise AdbError(f"ADB 命令超时: {' '.join(cmd)}") from exc

        if check and result.returncode != 0:
            detail = result.stderr.decode("utf-8", errors="replace").strip()
            raise AdbError(f"ADB 失败 ({result.returncode}): {detail}")
        return result

    def _build_cmd(self, args: Sequence[str], use_serial: bool = True) -> list[str]:
        cmd = [self._adb]
        if use_serial and self._serial:
            cmd.extend(["-s", self._serial])
        cmd.extend(args)
        return cmd
