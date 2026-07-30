"""生成单张 A4 可打印的 AprilTag 图片（tag36h11，OpenCV 原生渲染）"""

import numpy as np
import cv2
from pathlib import Path


# ─── 参数 ───────────────────────────────────────────
TAG_SIZE_MM_NOM = 160     # 标称 tag 边长（mm，打印参考值）
A4_W_MM = 210
A4_H_MM = 297
DPI = 300

A4_W = int(A4_W_MM / 25.4 * DPI)
A4_H = int(A4_H_MM / 25.4 * DPI)
TAG_PX = int(TAG_SIZE_MM_NOM / 25.4 * DPI)

# 打印后实际 tag 编码区边长（用于 PnP，与像素严格对应）
TAG_SIZE_MM = TAG_PX / DPI * 25.4

# OpenCV AprilTag 词典
DICT = cv2.aruco.DICT_APRILTAG_36H11
DICT_NAME = "tag36h11"

# 生成的 tag ID 列表
TAG_IDS = list(range(36))


def generate_tag_image(tag_id: int, tag_px: int) -> np.ndarray:
    """用 OpenCV 生成单个 tag（OpenCV 原生输出，无额外边框）"""
    d = cv2.aruco.getPredefinedDictionary(DICT)
    return cv2.aruco.generateImageMarker(d, tag_id, tag_px)


def generate_a4_page(tag_id: int, output_dir: str | Path, tag_size_mm: float = TAG_SIZE_MM):
    """
    生成一张 A4 纸可打印的 AprilTag。
    tag 居中放置，带裁剪参考线和标签。
    """
    tag_px = int(tag_size_mm / 25.4 * DPI)

    # 生成带边框的 tag
    tag_img = generate_tag_image(tag_id, tag_px)

    # A4 画布
    canvas = np.ones((A4_H, A4_W), dtype=np.uint8) * 255

    # 居中放置
    oh, ow = tag_img.shape
    ox = (A4_W - ow) // 2
    oy = (A4_H - oh) // 2
    if oy > 0 and ox > 0:
        canvas[oy:oy + oh, ox:ox + ow] = tag_img

    # 裁剪参考线（四角标记）
    margin_px = int(20 / 25.4 * DPI)
    grey = (160,)
    l_px = 60
    m = margin_px
    corners = [
        ((m, m + l_px), (m, m)),
        ((m, m), (m + l_px, m)),
        ((A4_W - m - l_px, m), (A4_W - m, m)),
        ((A4_W - m, m), (A4_W - m, m + l_px)),
        ((m, A4_H - m - l_px), (m, A4_H - m)),
        ((m, A4_H - m), (m + l_px, A4_H - m)),
        ((A4_W - m - l_px, A4_H - m), (A4_W - m, A4_H - m)),
        ((A4_W - m, A4_H - m - l_px), (A4_W - m, A4_H - m)),
    ]
    for pt1, pt2 in corners:
        cv2.line(canvas, pt1, pt2, grey, 3)

    # 标签文字
    actual_mm = TAG_SIZE_MM
    label = f"AprilTag {DICT_NAME}  ID:{tag_id}  {actual_mm:.1f}mm"
    cv2.putText(canvas, label, (margin_px, A4_H - margin_px // 2),
                cv2.FONT_HERSHEY_SIMPLEX, 1.0, grey, 2)

    # 保存
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"tag_{tag_id:02d}.png"
    cv2.imwrite(str(path), canvas)

    # 设置 DPI
    try:
        from PIL import Image
        Image.open(str(path)).save(str(path), dpi=(DPI, DPI))
    except ImportError:
        pass

    print(f"已生成: {path.name}  ({A4_W_MM}×{A4_H_MM}mm @ {DPI}DPI, tag={TAG_SIZE_MM:.2f}mm)")
    return path


def generate_all(output_dir: str | Path = "tags", tag_size_mm: float = TAG_SIZE_MM,
                 ids: list[int] | None = None):
    if ids is None:
        ids = TAG_IDS[:6]
    for tid in ids:
        generate_a4_page(tid, output_dir, tag_size_mm)
    actual = TAG_SIZE_MM
    print(f"\n共生成 {len(ids)} 个 tag（{DICT_NAME}）。")
    print(f"打印后 tag 编码区边长 = {actual:.2f} mm（{TAG_PX}px @ {DPI}DPI）")
    print(f"PnP 使用的 tag_size = {actual:.2f} mm — 两者严格一致")


if __name__ == "__main__":
    generate_all()
