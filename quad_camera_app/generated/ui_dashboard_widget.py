# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'dashboard_widget.ui'
##
## Created by: Qt User Interface Compiler version 6.11.1
##
## WARNING! All changes made in this file will be lost when recompiling UI file!
################################################################################

from PySide6.QtCore import (QCoreApplication, QDate, QDateTime, QLocale,
    QMetaObject, QObject, QPoint, QRect,
    QSize, QTime, QUrl, Qt)
from PySide6.QtGui import (QBrush, QColor, QConicalGradient, QCursor,
    QFont, QFontDatabase, QGradient, QIcon,
    QImage, QKeySequence, QLinearGradient, QPainter,
    QPalette, QPixmap, QRadialGradient, QTransform)
from PySide6.QtWidgets import (QApplication, QFormLayout, QGroupBox, QLabel,
    QSizePolicy, QVBoxLayout, QWidget)

class Ui_DashboardWidget(object):
    def setupUi(self, DashboardWidget):
        if not DashboardWidget.objectName():
            DashboardWidget.setObjectName(u"DashboardWidget")
        self.mainLayout = QVBoxLayout(DashboardWidget)
        self.mainLayout.setSpacing(6)
        self.mainLayout.setObjectName(u"mainLayout")
        self.mainLayout.setContentsMargins(4, 4, 4, 4)
        self.groupIMU = QGroupBox(DashboardWidget)
        self.groupIMU.setObjectName(u"groupIMU")
        self.groupIMU.setStyleSheet(u"QGroupBox { font: bold 13px; color: #0af; border: 1px solid #444; border-radius: 4px; margin-top: 10px; padding-top: 14px; } QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 4px; }")
        self.imuLayout = QFormLayout(self.groupIMU)
        self.imuLayout.setSpacing(2)
        self.imuLayout.setObjectName(u"imuLayout")
        self.labelQuat = QLabel(self.groupIMU)
        self.labelQuat.setObjectName(u"labelQuat")
        self.labelQuat.setStyleSheet(u"color: #aaa; font: 11px;")

        self.imuLayout.setWidget(0, QFormLayout.ItemRole.LabelRole, self.labelQuat)

        self.valueQuat = QLabel(self.groupIMU)
        self.valueQuat.setObjectName(u"valueQuat")
        self.valueQuat.setStyleSheet(u"color: #fff; font: 11px; font-family: monospace;")

        self.imuLayout.setWidget(0, QFormLayout.ItemRole.FieldRole, self.valueQuat)

        self.labelGyro = QLabel(self.groupIMU)
        self.labelGyro.setObjectName(u"labelGyro")
        self.labelGyro.setStyleSheet(u"color: #aaa; font: 11px;")

        self.imuLayout.setWidget(1, QFormLayout.ItemRole.LabelRole, self.labelGyro)

        self.valueGyro = QLabel(self.groupIMU)
        self.valueGyro.setObjectName(u"valueGyro")
        self.valueGyro.setStyleSheet(u"color: #fff; font: 11px; font-family: monospace;")

        self.imuLayout.setWidget(1, QFormLayout.ItemRole.FieldRole, self.valueGyro)

        self.labelAccel = QLabel(self.groupIMU)
        self.labelAccel.setObjectName(u"labelAccel")
        self.labelAccel.setStyleSheet(u"color: #aaa; font: 11px;")

        self.imuLayout.setWidget(2, QFormLayout.ItemRole.LabelRole, self.labelAccel)

        self.valueAccel = QLabel(self.groupIMU)
        self.valueAccel.setObjectName(u"valueAccel")
        self.valueAccel.setStyleSheet(u"color: #fff; font: 11px; font-family: monospace;")

        self.imuLayout.setWidget(2, QFormLayout.ItemRole.FieldRole, self.valueAccel)

        self.labelRPY = QLabel(self.groupIMU)
        self.labelRPY.setObjectName(u"labelRPY")
        self.labelRPY.setStyleSheet(u"color: #aaa; font: 11px;")

        self.imuLayout.setWidget(3, QFormLayout.ItemRole.LabelRole, self.labelRPY)

        self.valueRPY = QLabel(self.groupIMU)
        self.valueRPY.setObjectName(u"valueRPY")
        self.valueRPY.setStyleSheet(u"color: #fff; font: 11px; font-family: monospace;")

        self.imuLayout.setWidget(3, QFormLayout.ItemRole.FieldRole, self.valueRPY)


        self.mainLayout.addWidget(self.groupIMU)

        self.groupBattery = QGroupBox(DashboardWidget)
        self.groupBattery.setObjectName(u"groupBattery")
        self.groupBattery.setStyleSheet(u"QGroupBox { font: bold 13px; color: #0f0; border: 1px solid #444; border-radius: 4px; margin-top: 10px; padding-top: 14px; } QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 4px; }")
        self.batteryLayout = QFormLayout(self.groupBattery)
        self.batteryLayout.setSpacing(2)
        self.batteryLayout.setObjectName(u"batteryLayout")
        self.labelBatteryLevel = QLabel(self.groupBattery)
        self.labelBatteryLevel.setObjectName(u"labelBatteryLevel")
        self.labelBatteryLevel.setStyleSheet(u"color: #aaa; font: 11px;")

        self.batteryLayout.setWidget(0, QFormLayout.ItemRole.LabelRole, self.labelBatteryLevel)

        self.valueBatteryLevel = QLabel(self.groupBattery)
        self.valueBatteryLevel.setObjectName(u"valueBatteryLevel")
        self.valueBatteryLevel.setStyleSheet(u"color: #fff; font: 11px; font-family: monospace;")

        self.batteryLayout.setWidget(0, QFormLayout.ItemRole.FieldRole, self.valueBatteryLevel)


        self.mainLayout.addWidget(self.groupBattery)

        self.groupMotors = QGroupBox(DashboardWidget)
        self.groupMotors.setObjectName(u"groupMotors")
        self.groupMotors.setStyleSheet(u"QGroupBox { font: bold 13px; color: #fa0; border: 1px solid #444; border-radius: 4px; margin-top: 10px; padding-top: 14px; } QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 4px; }")
        self.motorLayout = QVBoxLayout(self.groupMotors)
        self.motorLayout.setSpacing(2)
        self.motorLayout.setObjectName(u"motorLayout")

        self.mainLayout.addWidget(self.groupMotors)

        self.groupVoice = QGroupBox(DashboardWidget)
        self.groupVoice.setObjectName(u"groupVoice")
        self.groupVoice.setStyleSheet(u"QGroupBox { font: bold 13px; color: #f0a; border: 1px solid #444; border-radius: 4px; margin-top: 10px; padding-top: 14px; } QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 4px; }")
        self.voiceLayout = QFormLayout(self.groupVoice)
        self.voiceLayout.setSpacing(2)
        self.voiceLayout.setObjectName(u"voiceLayout")
        self.labelVoiceData = QLabel(self.groupVoice)
        self.labelVoiceData.setObjectName(u"labelVoiceData")
        self.labelVoiceData.setStyleSheet(u"color: #aaa; font: 11px;")

        self.voiceLayout.setWidget(0, QFormLayout.ItemRole.LabelRole, self.labelVoiceData)

        self.valueVoiceData = QLabel(self.groupVoice)
        self.valueVoiceData.setObjectName(u"valueVoiceData")
        self.valueVoiceData.setStyleSheet(u"color: #fff; font: 11px; font-family: monospace;")

        self.voiceLayout.setWidget(0, QFormLayout.ItemRole.FieldRole, self.valueVoiceData)

        self.labelVoiceAngle = QLabel(self.groupVoice)
        self.labelVoiceAngle.setObjectName(u"labelVoiceAngle")
        self.labelVoiceAngle.setStyleSheet(u"color: #aaa; font: 11px;")

        self.voiceLayout.setWidget(1, QFormLayout.ItemRole.LabelRole, self.labelVoiceAngle)

        self.valueVoiceAngle = QLabel(self.groupVoice)
        self.valueVoiceAngle.setObjectName(u"valueVoiceAngle")
        self.valueVoiceAngle.setStyleSheet(u"color: #fff; font: 11px; font-family: monospace;")

        self.voiceLayout.setWidget(1, QFormLayout.ItemRole.FieldRole, self.valueVoiceAngle)


        self.mainLayout.addWidget(self.groupVoice)


        self.retranslateUi(DashboardWidget)

        QMetaObject.connectSlotsByName(DashboardWidget)
    # setupUi

    def retranslateUi(self, DashboardWidget):
        self.groupIMU.setTitle(QCoreApplication.translate("DashboardWidget", u"IMU", None))
        self.labelQuat.setText(QCoreApplication.translate("DashboardWidget", u"\u56db\u5143\u6570", None))
        self.valueQuat.setText(QCoreApplication.translate("DashboardWidget", u"-", None))
        self.labelGyro.setText(QCoreApplication.translate("DashboardWidget", u"\u9640\u87ba\u4eea(rad/s)", None))
        self.valueGyro.setText(QCoreApplication.translate("DashboardWidget", u"-", None))
        self.labelAccel.setText(QCoreApplication.translate("DashboardWidget", u"\u52a0\u901f\u5ea6(m/s\u00b2)", None))
        self.valueAccel.setText(QCoreApplication.translate("DashboardWidget", u"-", None))
        self.labelRPY.setText(QCoreApplication.translate("DashboardWidget", u"\u6b27\u62c9\u89d2(rad)", None))
        self.valueRPY.setText(QCoreApplication.translate("DashboardWidget", u"-", None))
        self.groupBattery.setTitle(QCoreApplication.translate("DashboardWidget", u"\u7535\u6c60", None))
        self.labelBatteryLevel.setText(QCoreApplication.translate("DashboardWidget", u"\u7535\u91cf", None))
        self.valueBatteryLevel.setText(QCoreApplication.translate("DashboardWidget", u"-", None))
        self.groupMotors.setTitle(QCoreApplication.translate("DashboardWidget", u"\u7535\u673a\u72b6\u6001", None))
        self.groupVoice.setTitle(QCoreApplication.translate("DashboardWidget", u"\u8bed\u97f3", None))
        self.labelVoiceData.setText(QCoreApplication.translate("DashboardWidget", u"\u97f3\u9891\u6570\u636e", None))
        self.valueVoiceData.setText(QCoreApplication.translate("DashboardWidget", u"-", None))
        self.labelVoiceAngle.setText(QCoreApplication.translate("DashboardWidget", u"\u89d2\u5ea6(\u00b0)", None))
        self.valueVoiceAngle.setText(QCoreApplication.translate("DashboardWidget", u"-", None))
        pass
    # retranslateUi

