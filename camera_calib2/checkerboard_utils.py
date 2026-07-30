"""棋盘格参数配置"""

INNER_CORNERS_W = 9
INNER_CORNERS_H = 6
SQUARE_SIZE_MM = 25


def get_calib_config():
    return {
        "pattern_size": (INNER_CORNERS_W, INNER_CORNERS_H),
        "square_size_mm": SQUARE_SIZE_MM,
    }
