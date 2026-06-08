"""示例流程：按需复制并改成自己的业务逻辑。"""

from __future__ import annotations

import logging
from pathlib import Path

from core.capture import ScreenCapture
from core.config import AppConfig
from core.input import InputController
from core.matcher import TemplateMatcher
from core.state_machine import StateMachine

logger = logging.getLogger(__name__)


def build_demo_flow(
    config: AppConfig,
    capture: ScreenCapture,
    matcher: TemplateMatcher,
    input_ctrl: InputController,
) -> StateMachine:
    """
    示例状态机:
      idle -> 若匹配 start.png 则点击 -> done
    你可以按同样方式扩展更多状态。
    """

    def on_idle() -> str | None:
        screen = capture.grab(save_debug=True)
        result = matcher.find(screen, "start.png")
        if result:
            input_ctrl.tap(*result.center)
            return "done"
        logger.info("等待 start.png 出现...")
        return "idle"

    sm = StateMachine()
    sm.register("idle", on_idle)
    sm.register("done", lambda: None)
    return sm


def list_templates(templates_dir: str) -> list[str]:
    return [p.name for p in Path(templates_dir).glob("*.png")]
