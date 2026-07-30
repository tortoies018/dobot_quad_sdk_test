"""生成可打印的相机标定棋盘格 (PNG, A4 尺寸)"""

import sys
from pathlib import Path

from checkerboard_utils import generate_checkerboard


def main():
    """保存棋盘格到当前目录"""
    out = Path(__file__).resolve().parent / "checkerboard.png"
    generate_checkerboard(str(out))

    print(f"\n文件位置: {out}")
    print("请用 A4 纸打印此图片，保持原始比例（不缩放）。")


if __name__ == "__main__":
    main()
