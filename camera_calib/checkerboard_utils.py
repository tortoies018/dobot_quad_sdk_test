"""棋盘格生成器——生成 A4 可打印的标定棋盘格 PNG"""

import numpy as np
import cv2
from pathlib import Path


# 棋盘格参数
INNER_CORNERS_W = 9        # 内角点数（宽）
INNER_CORNERS_H = 6        # 内角点数（高）
SQUARE_SIZE_MM = 25        # 每格边长（毫米）

# A4 纸张参数 (mm)
A4_W_MM = 297
A4_H_MM = 210

# 输出分辨率 (DPI)
DPI = 300

# 计算像素尺寸
SQUARE_SIZE_PX = int(SQUARE_SIZE_MM / 25.4 * DPI)   # 每格像素
BOARD_W_PX = (INNER_CORNERS_W + 1) * SQUARE_SIZE_PX  # 棋盘总宽
BOARD_H_PX = (INNER_CORNERS_H + 1) * SQUARE_SIZE_PX  # 棋盘总高
A4_W_PX = int(A4_W_MM / 25.4 * DPI)                  # A4 宽像素
A4_H_PX = int(A4_H_MM / 25.4 * DPI)                  # A4 高像素


def generate_checkerboard(save_path: str = "checkerboard.png"):
    """
    生成棋盘格标定图案并保存为 PNG。

    棋盘格位于 A4 画布居中位置，四周留白边距。
    """
    # 创建白色 A4 画布
    canvas = np.ones((A4_H_PX, A4_W_PX, 3), dtype=np.uint8) * 255

    # 计算棋盘格在 A4 画布上的偏移（居中）
    offset_x = (A4_W_PX - BOARD_W_PX) // 2
    offset_y = (A4_H_PX - BOARD_H_PX) // 2

    # 绘制棋盘格
    for row in range(INNER_CORNERS_H + 1):
        for col in range(INNER_CORNERS_W + 1):
            # 黑白交替
            is_black = (row + col) % 2 == 0
            color = 0 if is_black else 255

            x1 = offset_x + col * SQUARE_SIZE_PX
            y1 = offset_y + row * SQUARE_SIZE_PX
            x2 = x1 + SQUARE_SIZE_PX
            y2 = y1 + SQUARE_SIZE_PX

            canvas[y1:y2, x1:x2] = color

    # 绘制外边框（红色，便于裁剪参考）
    cv2.rectangle(canvas,
                  (offset_x, offset_y),
                  (offset_x + BOARD_W_PX, offset_y + BOARD_H_PX),
                  (0, 0, 255), 2)

    # 保存（设置 DPI 元数据以便打印）
    cv2.imwrite(save_path, canvas)

    # 使用 PIL 设置 DPI（OpenCV 不保留 DPI 信息）
    _set_png_dpi(save_path, DPI)

    # 输出参数信息
    print(f"棋盘格已保存: {save_path}")
    print(f"  内角点数: {INNER_CORNERS_W}×{INNER_CORNERS_H}")
    print(f"  方格尺寸: {SQUARE_SIZE_MM}mm (打印时)")
    print(f"  棋盘尺寸: {BOARD_W_MM:.1f}×{BOARD_H_MM:.1f}mm")
    print(f"  A4 画布: {A4_W_MM}×{A4_H_MM}mm @ {DPI}DPI")
    print(f"  图片像素: {A4_W_PX}×{A4_H_PX}")
    print(f"  棋盘偏移（居中）: ({offset_x}, {offset_y})")
    print(f"")
    print(f"标定时使用棋盘格内角点尺寸: ({INNER_CORNERS_W}, {INNER_CORNERS_H})")
    print(f"方格实际边长: {SQUARE_SIZE_MM}mm")


def _set_png_dpi(path: str, dpi: int):
    """使用 PIL 设置 PNG 文件的 DPI 元数据"""
    try:
        from PIL import Image
        img = Image.open(path)
        img.save(path, dpi=(dpi, dpi))
    except ImportError:
        print("提示: 安装 Pillow 可设置 DPI: pip install Pillow")


# ---- 导出常量供标定程序使用 ----
def get_calib_config():
    """返回棋盘格配置字典，供标定程序使用"""
    return {
        "pattern_size": (INNER_CORNERS_W, INNER_CORNERS_H),
        "square_size_mm": SQUARE_SIZE_MM,
        "dpi": DPI,
    }


BOARD_W_MM = (INNER_CORNERS_W + 1) * SQUARE_SIZE_MM
BOARD_H_MM = (INNER_CORNERS_H + 1) * SQUARE_SIZE_MM


if __name__ == "__main__":
    out = Path(__file__).resolve().parent / "checkerboard.png"
    generate_checkerboard(str(out))
