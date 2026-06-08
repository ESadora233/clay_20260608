"""在截图上点击取相对坐标。"""

from __future__ import annotations

import cv2
import numpy as np


def pick_point_ratio(image: np.ndarray, window_title: str = "pick-point") -> tuple[float, float]:
    height, width = image.shape[:2]
    picked: dict[str, int] = {}
    display = image.copy()

    def redraw() -> None:
        overlay = display.copy()
        if "x" in picked:
            x, y = picked["x"], picked["y"]
            cv2.circle(overlay, (x, y), 18, (0, 0, 255), 3)
            cv2.putText(
                overlay,
                f"({x},{y}) ratio=({x/width:.3f},{y/height:.3f})",
                (x + 10, max(y - 12, 20)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (0, 255, 255),
                2,
            )
        cv2.imshow(window_title, overlay)

    def on_mouse(event: int, x: int, y: int, _flags: int, _param) -> None:
        if event != cv2.EVENT_LBUTTONDOWN:
            return
        picked["x"] = x
        picked["y"] = y
        redraw()

    cv2.namedWindow(window_title, cv2.WINDOW_NORMAL)
    redraw()
    cv2.setMouseCallback(window_title, on_mouse)
    print("点击 W 技能按钮位置，满意后按 Enter 确认，Esc 取消")

    while True:
        key = cv2.waitKey(50) & 0xFF
        if key == 27:
            cv2.destroyAllWindows()
            raise SystemExit("已取消")
        if key in (13, 10):
            if "x" not in picked:
                print("请先点击目标位置")
                continue
            break

    cv2.destroyAllWindows()
    return picked["x"] / width, picked["y"] / height
