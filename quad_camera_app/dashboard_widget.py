from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QLabel, QVBoxLayout, QHBoxLayout

from generated.ui_dashboard_widget import Ui_DashboardWidget


MOTOR_LABELS = [
    "FL0", "FL1", "FL2", "FL3",
    "FR0", "FR1", "FR2", "FR3",
    "HL0", "HL1", "HL2", "HL3",
    "HR0", "HR1", "HR2", "HR3",
]


class DashboardWidget(QWidget, Ui_DashboardWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setupUi(self)

        self._motor_labels = []
        for i in range(16):
            row = QHBoxLayout()
            name = QLabel(f"M{i:02d}({MOTOR_LABELS[i]}):")
            name.setStyleSheet("color: #a8b3bc; font: 10px monospace;")
            name.setFixedWidth(90)
            val = QLabel("-")
            val.setStyleSheet("color: #fff; font: 10px monospace;")
            val.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            row.addWidget(name)
            row.addWidget(val, 1)
            self.motorLayout.addLayout(row)
            self._motor_labels.append(val)

        spacer = self.motorLayout.itemAt(self.motorLayout.count() - 1)
        if spacer:
            spacer_spacer = spacer.spacerItem()
            if spacer_spacer:
                self.motorLayout.removeItem(spacer)

    def update_imu(self, quat, gyro, accel, rpy):
        self.valueQuat.setText(
            f"[{quat[0]:.4f}, {quat[1]:.4f}, {quat[2]:.4f}, {quat[3]:.4f}]"
        )
        self.valueGyro.setText(
            f"[{gyro[0]:.3f}, {gyro[1]:.3f}, {gyro[2]:.3f}]"
        )
        self.valueAccel.setText(
            f"[{accel[0]:.2f}, {accel[1]:.2f}, {accel[2]:.2f}]"
        )
        self.valueRPY.setText(
            f"[{rpy[0]:.3f}, {rpy[1]:.3f}, {rpy[2]:.3f}]"
        )

    def update_battery(self, level):
        self.valueBatteryLevel.setText(f"{level}%")

    def update_motor(self, idx, mode, q, dq, tau, temp):
        if 0 <= idx < len(self._motor_labels):
            self._motor_labels[idx].setText(
                f"mode={mode} q={q:.3f} dq={dq:.3f} τ={tau:.3f} T={temp}°C"
            )

    def update_voice(self, data_size, angle):
        self.valueVoiceData.setText(f"{data_size} bytes" if data_size >= 0 else "-")
        self.valueVoiceAngle.setText(f"{angle:.1f}°" if angle >= 0 else "-")
