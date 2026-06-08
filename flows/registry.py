"""流程注册表。"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from core.capture import ScreenCapture
from core.config import AppConfig
from core.input import InputController
from core.matcher import TemplateMatcher
from core.state_machine import StateMachine

from flows.demo_flow import build_demo_flow
from flows.farm_flow import build_farm_flow

FlowBuilder = Callable[
    [AppConfig, ScreenCapture, TemplateMatcher, InputController, int],
    StateMachine,
]


def _wrap_demo(
    config: AppConfig,
    capture: ScreenCapture,
    matcher: TemplateMatcher,
    input_ctrl: InputController,
    _max_rounds: int,
) -> StateMachine:
    return build_demo_flow(config, capture, matcher, input_ctrl)


def _wrap_farm(
    config: AppConfig,
    capture: ScreenCapture,
    matcher: TemplateMatcher,
    input_ctrl: InputController,
    max_rounds: int,
) -> StateMachine:
    return build_farm_flow(config, capture, matcher, input_ctrl, max_rounds=max_rounds)


FLOW_REGISTRY: dict[str, FlowBuilder] = {
    "demo": _wrap_demo,
    "farm": _wrap_farm,
}


def get_flow_builder(name: str) -> FlowBuilder:
    if name not in FLOW_REGISTRY:
        available = ", ".join(sorted(FLOW_REGISTRY))
        raise KeyError(f"未知流程 '{name}'，可选: {available}")
    return FLOW_REGISTRY[name]
