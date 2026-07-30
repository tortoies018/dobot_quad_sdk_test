"""AprilTag 标定板生成器——生成 6×6 tagStandard41h12 棋盘"""

import ctypes
import numpy as np
import cv2
from pathlib import Path


# 板面参数
TAG_GRID = (6, 6)        # 行数 × 列数
TAG_SIZE_MM = 88          # 每个 tag 边长（mm）
SPACING_MM = 26.4         # tag 间距（mm）
DPI = 300                 # 输出分辨率

BOARD_W_MM = TAG_GRID[1] * TAG_SIZE_MM + (TAG_GRID[1] - 1) * SPACING_MM
BOARD_H_MM = TAG_GRID[0] * TAG_SIZE_MM + (TAG_GRID[0] - 1) * SPACING_MM


def _load_family():
    """通过 ctypes 加载 tagStandard41h12 标签族"""
    lib = ctypes.CDLL(str(
        Path.home() / ".local/lib/python3.10/site-packages/pupil_apriltags/lib64/libapriltag.so"
    ))
    lib.tagStandard41h12_create.restype = ctypes.c_void_p
    ptr = lib.tagStandard41h12_create()

    ncodes = ctypes.c_uint32.from_address(ptr).value
    codes_ptr = ctypes.c_void_p.from_address(ptr + 8).value
    width_at_border = ctypes.c_uint32.from_address(ptr + 16).value
    total_width = ctypes.c_uint32.from_address(ptr + 20).value
    codes = (ctypes.c_uint64 * ncodes).from_address(codes_ptr)
    return codes, total_width, width_at_border


def _render_tag(code, tag_px, border_bits=2):
    """将 tag 的二进制编码渲染为图像，四边加白色边框"""
    W_BITS = 9  # tagStandard41h12 是 9×9 bit
    bit_h = tag_px // W_BITS

    img = np.ones((tag_px, tag_px), dtype=np.uint8) * 255
    for r in range(W_BITS):
        for c in range(W_BITS):
            bit = (code >> (r * W_BITS + c)) & 1
            if bit:
                y1, x1 = r * bit_h, c * bit_h
                img[y1:y1 + bit_h, x1:x1 + bit_h] = 0

    return img


def generate_board(save_path: str = "apriltag_board.png"):
    """生成 6×6 AprilTag 标定板并保存为 PNG"""

    codes, W_bits, _ = _load_family()

    PX_PER_MM = DPI / 25.4
    tag_px = int(TAG_SIZE_MM * PX_PER_MM)
    spacing_px = int(SPACING_MM * PX_PER_MM)

    board_w_px = TAG_GRID[1] * tag_px + (TAG_GRID[1] - 1) * spacing_px
    board_h_px = TAG_GRID[0] * tag_px + (TAG_GRID[0] - 1) * spacing_px

    canvas = np.ones((board_h_px, board_w_px), dtype=np.uint8) * 255

    tag_id = 0
    for row in range(TAG_GRID[0]):
        for col in range(TAG_GRID[1]):
            y = row * (tag_px + spacing_px)
            x = col * (tag_px + spacing_px)

            tag_img = _render_tag(codes[tag_id], tag_px)
            canvas[y:y + tag_px, x:x + tag_px] = tag_img
            tag_id += 1

            if tag_id >= min(2115, 36):
                break
        if tag_id >= 36:
            break

    cv2.imwrite(save_path, canvas)

    # 用 PIL 设置 DPI
    try:
        from PIL import Image
        Image.open(save_path).save(save_path, dpi=(DPI, DPI))
    except ImportError:
        pass

    print(f"标定板已保存: {save_path}")
    print(f"  Tag 族: tagStandard41h12")
    print(f"  规格: {TAG_GRID[0]}×{TAG_GRID[1]} (共 {tag_id} 个 tag)")
    print(f"  Tag 边长: {TAG_SIZE_MM} mm")
    print(f"  间距: {SPACING_MM} mm")
    print(f"  板面尺寸: {BOARD_W_MM:.1f}×{BOARD_H_MM:.1f} mm")
    print(f"  DPI: {DPI}")
    print(f"  图片像素: {board_w_px}×{board_h_px}")


def get_calib_config():
    """返回标定配置供程序使用"""
    return {
        "tag_grid": TAG_GRID,
        "tag_size_mm": TAG_SIZE_MM,
        "spacing_mm": SPACING_MM,
    }
