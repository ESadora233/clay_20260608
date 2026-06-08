# clay_20260608

基于 **Python + 应用宝模拟器 + ADB** 的通用屏幕自动化框架。

可用于学习图像识别自动化流程（截图 → 模板匹配 → 点击）。请仅在合法、合规的场景下使用。

## 环境要求

- Windows 10/11
- Python 3.10+
- Android Platform Tools (`adb`)
- 应用宝模拟器，已开启 ADB 调试

## 安装

```powershell
cd d:\gitData\clay_20260608
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

### 安装 adb（若提示找不到 adb）

任选一种方式：

```powershell
# 方式 1：一键下载到项目目录（推荐）
powershell -ExecutionPolicy Bypass -File scripts\setup_adb.ps1

# 方式 2：手动下载后配置路径
# 在 config.yaml 设置 adb.executable: "D:\path\to\adb.exe"
```

安装后运行诊断：

```powershell
python main.py doctor
```

## 应用宝 ADB 配置

1. 打开应用宝模拟器
2. 在设置中开启 **ADB 调试**，记下端口（应用宝一般为 **`5555`**，不是 5037）
3. 修改 `config.yaml` 中的 `adb.host` / `adb.port`
4. 连接设备：

```bash
python main.py connect
adb devices
```

若 `adb devices` 显示多个设备，在 `config.yaml` 里设置 `adb.serial`。

**建议**：模拟器分辨率固定为 **1280×720**，之后不要随意更改，否则模板需重做。

## 使用步骤

### 1. 截取屏幕

```bash
python main.py screenshot
```

截图保存在 `runtime/screenshots/manual.png`。

### 2. 制作模板（crop 命令）

**方式 A：从已有截图框选裁切**

```powershell
python main.py crop dungeon_entry
python main.py crop confirm runtime/screenshots/manual.png
```

弹出窗口后，用鼠标框选按钮区域，按 **Enter** 确认。

**方式 B：先截设备屏幕再裁切**

```powershell
python main.py crop dungeon_entry --live
```

**方式 C：指定坐标（无弹窗）**

```powershell
python main.py crop confirm manual.png --region 100,200,80,40
```

模板保存在 `assets/templates/`，越小越好。

### 3. 测试匹配

```bash
python main.py match start.png
python main.py match start.png --tap   # 匹配成功后自动点击
```

### 4. 运行自动化流程

```powershell
# 搬砖流程（编辑 flows/farm_flow.py 配置模板名与逻辑）
python main.py run
python main.py run farm --loops 10

# 示例流程
python main.py run demo
python main.py demo
```

## 项目结构

```
clay_20260608/
├── config.yaml           # ADB、阈值、超时等配置
├── main.py               # 命令行入口
├── requirements.txt
├── assets/templates/     # UI 模板图 (*.png)
├── core/
│   ├── adb.py            # ADB 连接与命令
│   ├── capture.py        # 截图
│   ├── matcher.py        # OpenCV 模板匹配
│   ├── input.py          # 点击/滑动
│   ├── state_machine.py  # 状态机
│   └── config.py         # 配置加载
├── flows/
│   ├── demo_flow.py      # 示例流程
│   ├── farm_flow.py      # 搬砖流程骨架
│   └── registry.py       # 流程注册
└── runtime/screenshots/  # 运行时截图（自动生成）
```

## 扩展自己的流程

在 `flows/` 下新建流程文件，用状态机串联步骤：

```python
def on_main_menu():
    screen = capture.grab()
    if matcher.find(screen, "dungeon.png"):
        input_ctrl.tap(x, y)
        return "in_dungeon"
    return "main_menu"
```

常用 API：

| 模块 | 方法 | 说明 |
|------|------|------|
| `ScreenCapture` | `grab()` | 截取屏幕 (BGR numpy) |
| `TemplateMatcher` | `find(screen, "x.png")` | 单次匹配 |
| `TemplateMatcher` | `wait_for(...)` | 轮询等待模板 |
| `InputController` | `tap(x, y)` | 点击 |
| `InputController` | `swipe(x1,y1,x2,y2)` | 滑动 |
| `StateMachine` | `register` / `run` | 状态流转 |

## 调参建议

| 参数 | 位置 | 说明 |
|------|------|------|
| `matcher.threshold` | config.yaml | 默认 0.85，误匹配多就调高，找不到就调低 |
| `runtime.action_delay` | config.yaml | 每次操作后等待时间 |
| `runtime.wait_timeout` | config.yaml | 等待界面超时 |

## 常见问题

**adb 找不到设备**

- 确认应用宝已启动且 ADB 已开启
- 手动执行 `adb connect 127.0.0.1:5555`
- **5037 是 PC 上 adb 服务端口**，不要 `adb connect 127.0.0.1:5037`（会显示 offline）
- 若误连了 5037：`adb disconnect 127.0.0.1:5037`
- 多设备时在 `config.yaml` 设置 `adb.serial`（如 `127.0.0.1:5555`）

**模板匹配失败**

- 分辨率是否与截模板时一致
- 模板是否过大/过小
- 适当调整 `matcher.threshold`

**截图黑屏**

- 确认模拟器窗口未最小化
- 尝试重启 ADB：`adb kill-server` 后再 `connect`

## 免责声明

本框架仅供技术学习与合法自动化测试。使用自动化工具操作网络游戏可能违反用户协议并导致封号，请自行承担风险。
