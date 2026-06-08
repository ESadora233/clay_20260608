"""从截图裁切模板图片。"""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np


def parse_region(text: str) -> tuple[int, int, int, int]:
    parts = [p.strip() for p in text.split(",")]
    if len(parts) != 4:
        raise ValueError("region 格式应为 x,y,width,height")
    return tuple(int(p) for p in parts)  # type: ignore[return-value]


def crop_image(
    source: Path,
    output: Path,
    region: tuple[int, int, int, int] | None = None,
) -> Path:
    image = cv2.imread(str(source), cv2.IMREAD_COLOR)
    if image is None:
        raise FileNotFoundError(f"无法读取图片: {source}")

    if region is None:
        cropped = _select_roi_interactive(image)
    else:
        x, y, w, h = region
        cropped = _crop_region(image, x, y, w, h)

    output.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(output), cropped):
        raise RuntimeError(f"保存失败: {output}")
    return output


def _crop_region(image: np.ndarray, x: int, y: int, w: int, h: int) -> np.ndarray:
    height, width = image.shape[:2]
    if w <= 0 or h <= 0:
        raise ValueError("宽高必须大于 0")
    if x < 0 or y < 0 or x + w > width or y + h > height:
        raise ValueError(f"区域越界: ({x},{y},{w},{h}) 图像尺寸 {width}x{height}")
    return image[y : y + h, x : x + w].copy()


def _select_roi_interactive(image: np.ndarray) -> np.ndarray:
    window = "crop - 框选后按 Enter 确认，按 c 取消"
    roi = cv2.selectROI(window, image, showCrosshair=True, fromCenter=False)
    cv2.destroyAllWindows()

    x, y, w, h = (int(v) for v in roi)
    if w <= 0 or h <= 0:
        raise SystemExit("未选择有效区域，已取消")

    return _crop_region(image, x, y, w, h)
