"""生成 AprilTag 标定板——打印在 A3 或两张 A4 拼接使用"""

from board_generator import generate_board


if __name__ == "__main__":
    generate_board("apriltag_board.png")
