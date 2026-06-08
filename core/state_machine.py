"""简单状态机，用于串联自动化流程。"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Callable

logger = logging.getLogger(__name__)

StateHandler = Callable[[], str | None]


@dataclass
class StateMachine:
    handlers: dict[str, StateHandler] = field(default_factory=dict)
    current: str = "idle"
    max_steps: int = 1000

    def register(self, state: str, handler: StateHandler) -> None:
        self.handlers[state] = handler

    def run(self, start: str | None = None) -> None:
        if start:
            self.current = start

        steps = 0
        while self.current and steps < self.max_steps:
            handler = self.handlers.get(self.current)
            if handler is None:
                raise KeyError(f"未注册状态: {self.current}")

            logger.info("进入状态: %s", self.current)
            next_state = handler()
            logger.info("状态转移: %s -> %s", self.current, next_state)
            self.current = next_state or ""
            steps += 1

        if steps >= self.max_steps:
            raise RuntimeError("状态机超过最大步数，可能存在死循环")

        logger.info("状态机结束")
