"""数据显示面板——展示机器人状态、位姿、关节和接触力"""

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QWidget, QLabel, QHBoxLayout

from generated.ui_data_panel import Ui_DataPanel


# 12 个关节的名称标签
JOINT_NAMES = [
    "FL0", "FL1", "FL2", "FL3",
    "FR0", "FR1", "FR2", "FR3",
    "HL0", "HL1", "HL2", "HL3",
    "HR0", "HR1", "HR2", "HR3",
]


class DataPanel(QWidget, Ui_DataPanel):
    """聚合所有机器人状态信息的面板控件"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setupUi(self)

        # 动态创建 16 个关节标签行
        self._joint_labels = []
        for i in range(16):
            row = QHBoxLayout()
            name = QLabel(f"M{i:02d} [{JOINT_NAMES[i]}]")
            name.setStyleSheet("color: #a8b3bc; font: 11px monospace;")
            name.setFixedWidth(100)
            # 位置 / 速度 / 力矩
            val = QLabel("—   —   —")
            val.setStyleSheet("color: #fff; font: 11px monospace;")
            val.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            row.addWidget(name)
            row.addWidget(val, 1)
            self.jointListLayout.addLayout(row)
            self._joint_labels.append(val)

        # 移除布局末尾可能存在的伸缩项
        spacer = self.jointListLayout.itemAt(self.jointListLayout.count() - 1)
        if spacer and spacer.spacerItem():
            self.jointListLayout.removeItem(spacer)

    # ---- 更新方法 ----

    def update_info(self, robot_type, fsm_state, speed_ratio, obstacle_avoid):
        """更新基本信息面板"""
        self.valRobotType.setText(robot_type if robot_type else "未知")
        self.valFSM.setText(fsm_state if fsm_state else "未知")
        self.valSpeed.setText(str(speed_ratio) if speed_ratio >= 0 else "-")

        if obstacle_avoid:
            self.valAvoid.setText("已开启")
            self.valAvoid.setStyleSheet("color: #69f0ae; font: bold 14px monospace;")
        else:
            self.valAvoid.setText("已关闭")
            self.valAvoid.setStyleSheet("color: #ef5350; font: bold 14px monospace;")

    def update_pose(self, pos, vel, accel, omega, rpy):
        """更新机体位姿面板"""
        self.valPos.setText(self._fmt_vec3(pos))
        self.valVel.setText(self._fmt_vec3(vel))
        self.valAccel.setText(self._fmt_vec3(accel))
        self.valOmega.setText(self._fmt_vec3(omega))
        self.valRPY.setText(self._fmt_vec3(rpy))

    def update_joints(self, jpos, jvel, jtau):
        """更新 16 个关节的位置/速度/力矩"""
        for i in range(16):
            q = jpos[i] if i < len(jpos) else 0.0
            dq = jvel[i] if i < len(jvel) else 0.0
            t = jtau[i] if i < len(jtau) else 0.0
            self._joint_labels[i].setText(f"q={q:.4f}  dq={dq:.4f}  τ={t:.4f}")

    def update_grf(self, grf_left, grf_right, grf_filtered):
        """更新足端接触力"""
        self.valGRFLeft.setText(self._fmt_vec3(grf_left))
        self.valGRFRight.setText(self._fmt_vec3(grf_right))
        if grf_filtered and len(grf_filtered) >= 2:
            self.valGRFFiltered.setText(f"[{grf_filtered[0]:.1f}, {grf_filtered[1]:.1f}]")
        else:
            self.valGRFFiltered.setText("-")

    @staticmethod
    def _fmt_vec3(v):
        """将三维向量格式化为 [x, y, z] 字符串"""
        if not v or len(v) < 3:
            return "-"
        return f"[{v[0]:.4f}, {v[1]:.4f}, {v[2]:.4f}]"
