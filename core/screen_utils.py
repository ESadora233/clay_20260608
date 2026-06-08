"""检测截图是否为黑屏/无效。"""

from __future__ import annotations

import numpy as np


def is_blank_screen(image: np.ndarray, mean_threshold: float = 1.0) -> bool:
    if image is None or image.size == 0:
        return True
    return float(image.mean()) < mean_threshold
