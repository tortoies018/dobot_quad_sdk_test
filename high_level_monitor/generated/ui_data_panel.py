# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'data_panel.ui'
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
from PySide6.QtWidgets import (QApplication, QFormLayout, QGridLayout, QGroupBox,
    QLabel, QSizePolicy, QVBoxLayout, QWidget)

class Ui_DataPanel(object):
    def setupUi(self, DataPanel):
        if not DataPanel.objectName():
            DataPanel.setObjectName(u"DataPanel")
        self.rootLayout = QVBoxLayout(DataPanel)
        self.rootLayout.setSpacing(6)
        self.rootLayout.setObjectName(u"rootLayout")
        self.rootLayout.setContentsMargins(6, 6, 6, 6)
        self.groupInfo = QGroupBox(DataPanel)
        self.groupInfo.setObjectName(u"groupInfo")
        self.groupInfo.setStyleSheet(u"QGroupBox { font: bold 14px; color: #0af; border: 1px solid #333; border-radius: 6px; margin-top: 12px; padding-top: 16px; background: #252525; } QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 6px; }")
        self.infoGrid = QGridLayout(self.groupInfo)
        self.infoGrid.setObjectName(u"infoGrid")
        self.infoGrid.setColumnMinimumWidth(0)
        self.lblRobotTypeTitle = QLabel(self.groupInfo)
        self.lblRobotTypeTitle.setObjectName(u"lblRobotTypeTitle")
        self.lblRobotTypeTitle.setStyleSheet(u"color: #888; font: 12px;")

        self.infoGrid.addWidget(self.lblRobotTypeTitle, 0, 0, 1, 1)

        self.valRobotType = QLabel(self.groupInfo)
        self.valRobotType.setObjectName(u"valRobotType")
        self.valRobotType.setStyleSheet(u"color: #fff; font: bold 14px; font-family: monospace;")

        self.infoGrid.addWidget(self.valRobotType, 0, 1, 1, 1)

        self.lblFSMTitle = QLabel(self.groupInfo)
        self.lblFSMTitle.setObjectName(u"lblFSMTitle")
        self.lblFSMTitle.setStyleSheet(u"color: #888; font: 12px;")

        self.infoGrid.addWidget(self.lblFSMTitle, 0, 2, 1, 1)

        self.valFSM = QLabel(self.groupInfo)
        self.valFSM.setObjectName(u"valFSM")
        self.valFSM.setStyleSheet(u"color: #0f0; font: bold 14px; font-family: monospace;")

        self.infoGrid.addWidget(self.valFSM, 0, 3, 1, 1)

        self.lblSpeedTitle = QLabel(self.groupInfo)
        self.lblSpeedTitle.setObjectName(u"lblSpeedTitle")
        self.lblSpeedTitle.setStyleSheet(u"color: #888; font: 12px;")

        self.infoGrid.addWidget(self.lblSpeedTitle, 1, 0, 1, 1)

        self.valSpeed = QLabel(self.groupInfo)
        self.valSpeed.setObjectName(u"valSpeed")
        self.valSpeed.setStyleSheet(u"color: #fff; font: bold 14px; font-family: monospace;")

        self.infoGrid.addWidget(self.valSpeed, 1, 1, 1, 1)

        self.lblAvoidTitle = QLabel(self.groupInfo)
        self.lblAvoidTitle.setObjectName(u"lblAvoidTitle")
        self.lblAvoidTitle.setStyleSheet(u"color: #888; font: 12px;")

        self.infoGrid.addWidget(self.lblAvoidTitle, 1, 2, 1, 1)

        self.valAvoid = QLabel(self.groupInfo)
        self.valAvoid.setObjectName(u"valAvoid")
        self.valAvoid.setStyleSheet(u"font: bold 14px; font-family: monospace;")

        self.infoGrid.addWidget(self.valAvoid, 1, 3, 1, 1)


        self.rootLayout.addWidget(self.groupInfo)

        self.groupPose = QGroupBox(DataPanel)
        self.groupPose.setObjectName(u"groupPose")
        self.groupPose.setStyleSheet(u"QGroupBox { font: bold 14px; color: #fa0; border: 1px solid #333; border-radius: 6px; margin-top: 12px; padding-top: 16px; background: #252525; } QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 6px; }")
        self.poseGrid = QGridLayout(self.groupPose)
        self.poseGrid.setObjectName(u"poseGrid")
        self.lblPosTitle = QLabel(self.groupPose)
        self.lblPosTitle.setObjectName(u"lblPosTitle")
        self.lblPosTitle.setStyleSheet(u"color: #888; font: 12px;")

        self.poseGrid.addWidget(self.lblPosTitle, 0, 0, 1, 1)

        self.valPos = QLabel(self.groupPose)
        self.valPos.setObjectName(u"valPos")
        self.valPos.setStyleSheet(u"color: #fff; font: 12px monospace;")

        self.poseGrid.addWidget(self.valPos, 0, 1, 1, 1)

        self.lblVelTitle = QLabel(self.groupPose)
        self.lblVelTitle.setObjectName(u"lblVelTitle")
        self.lblVelTitle.setStyleSheet(u"color: #888; font: 12px;")

        self.poseGrid.addWidget(self.lblVelTitle, 1, 0, 1, 1)

        self.valVel = QLabel(self.groupPose)
        self.valVel.setObjectName(u"valVel")
        self.valVel.setStyleSheet(u"color: #fff; font: 12px monospace;")

        self.poseGrid.addWidget(self.valVel, 1, 1, 1, 1)

        self.lblAccelTitle = QLabel(self.groupPose)
        self.lblAccelTitle.setObjectName(u"lblAccelTitle")
        self.lblAccelTitle.setStyleSheet(u"color: #888; font: 12px;")

        self.poseGrid.addWidget(self.lblAccelTitle, 2, 0, 1, 1)

        self.valAccel = QLabel(self.groupPose)
        self.valAccel.setObjectName(u"valAccel")
        self.valAccel.setStyleSheet(u"color: #fff; font: 12px monospace;")

        self.poseGrid.addWidget(self.valAccel, 2, 1, 1, 1)

        self.lblOmegaTitle = QLabel(self.groupPose)
        self.lblOmegaTitle.setObjectName(u"lblOmegaTitle")
        self.lblOmegaTitle.setStyleSheet(u"color: #888; font: 12px;")

        self.poseGrid.addWidget(self.lblOmegaTitle, 3, 0, 1, 1)

        self.valOmega = QLabel(self.groupPose)
        self.valOmega.setObjectName(u"valOmega")
        self.valOmega.setStyleSheet(u"color: #fff; font: 12px monospace;")

        self.poseGrid.addWidget(self.valOmega, 3, 1, 1, 1)

        self.lblRPYTitle = QLabel(self.groupPose)
        self.lblRPYTitle.setObjectName(u"lblRPYTitle")
        self.lblRPYTitle.setStyleSheet(u"color: #888; font: 12px;")

        self.poseGrid.addWidget(self.lblRPYTitle, 4, 0, 1, 1)

        self.valRPY = QLabel(self.groupPose)
        self.valRPY.setObjectName(u"valRPY")
        self.valRPY.setStyleSheet(u"color: #fff; font: 12px monospace;")

        self.poseGrid.addWidget(self.valRPY, 4, 1, 1, 1)


        self.rootLayout.addWidget(self.groupPose)

        self.groupJoints = QGroupBox(DataPanel)
        self.groupJoints.setObjectName(u"groupJoints")
        self.groupJoints.setStyleSheet(u"QGroupBox { font: bold 14px; color: #0f0; border: 1px solid #333; border-radius: 6px; margin-top: 12px; padding-top: 16px; background: #252525; } QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 6px; }")
        self.jointListLayout = QVBoxLayout(self.groupJoints)
        self.jointListLayout.setObjectName(u"jointListLayout")

        self.rootLayout.addWidget(self.groupJoints)

        self.groupGRF = QGroupBox(DataPanel)
        self.groupGRF.setObjectName(u"groupGRF")
        self.groupGRF.setStyleSheet(u"QGroupBox { font: bold 14px; color: #f0a; border: 1px solid #333; border-radius: 6px; margin-top: 12px; padding-top: 16px; background: #252525; } QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 6px; }")
        self.grfLayout = QFormLayout(self.groupGRF)
        self.grfLayout.setObjectName(u"grfLayout")
        self.lblGRFLeft = QLabel(self.groupGRF)
        self.lblGRFLeft.setObjectName(u"lblGRFLeft")
        self.lblGRFLeft.setStyleSheet(u"color: #888; font: 12px;")

        self.grfLayout.setWidget(0, QFormLayout.ItemRole.LabelRole, self.lblGRFLeft)

        self.valGRFLeft = QLabel(self.groupGRF)
        self.valGRFLeft.setObjectName(u"valGRFLeft")
        self.valGRFLeft.setStyleSheet(u"color: #fff; font: 12px monospace;")

        self.grfLayout.setWidget(0, QFormLayout.ItemRole.FieldRole, self.valGRFLeft)

        self.lblGRFRight = QLabel(self.groupGRF)
        self.lblGRFRight.setObjectName(u"lblGRFRight")
        self.lblGRFRight.setStyleSheet(u"color: #888; font: 12px;")

        self.grfLayout.setWidget(1, QFormLayout.ItemRole.LabelRole, self.lblGRFRight)

        self.valGRFRight = QLabel(self.groupGRF)
        self.valGRFRight.setObjectName(u"valGRFRight")
        self.valGRFRight.setStyleSheet(u"color: #fff; font: 12px monospace;")

        self.grfLayout.setWidget(1, QFormLayout.ItemRole.FieldRole, self.valGRFRight)

        self.lblGRFFiltered = QLabel(self.groupGRF)
        self.lblGRFFiltered.setObjectName(u"lblGRFFiltered")
        self.lblGRFFiltered.setStyleSheet(u"color: #888; font: 12px;")

        self.grfLayout.setWidget(2, QFormLayout.ItemRole.LabelRole, self.lblGRFFiltered)

        self.valGRFFiltered = QLabel(self.groupGRF)
        self.valGRFFiltered.setObjectName(u"valGRFFiltered")
        self.valGRFFiltered.setStyleSheet(u"color: #fff; font: 12px monospace;")

        self.grfLayout.setWidget(2, QFormLayout.ItemRole.FieldRole, self.valGRFFiltered)


        self.rootLayout.addWidget(self.groupGRF)


        self.retranslateUi(DataPanel)

        QMetaObject.connectSlotsByName(DataPanel)
    # setupUi

    def retranslateUi(self, DataPanel):
        self.groupInfo.setTitle(QCoreApplication.translate("DataPanel", u"\u57fa\u672c\u4fe1\u606f", None))
        self.lblRobotTypeTitle.setText(QCoreApplication.translate("DataPanel", u"\u673a\u5668\u4eba\u7c7b\u578b", None))
        self.valRobotType.setText(QCoreApplication.translate("DataPanel", u"-", None))
        self.lblFSMTitle.setText(QCoreApplication.translate("DataPanel", u"FSM \u72b6\u6001", None))
        self.valFSM.setText(QCoreApplication.translate("DataPanel", u"-", None))
        self.lblSpeedTitle.setText(QCoreApplication.translate("DataPanel", u"\u901f\u5ea6\u6bd4", None))
        self.valSpeed.setText(QCoreApplication.translate("DataPanel", u"-", None))
        self.lblAvoidTitle.setText(QCoreApplication.translate("DataPanel", u"\u907f\u969c", None))
        self.valAvoid.setText(QCoreApplication.translate("DataPanel", u"-", None))
        self.groupPose.setTitle(QCoreApplication.translate("DataPanel", u"\u673a\u4f53\u4f4d\u59ff", None))
        self.lblPosTitle.setText(QCoreApplication.translate("DataPanel", u"\u4f4d\u7f6e (m)", None))
        self.valPos.setText(QCoreApplication.translate("DataPanel", u"-", None))
        self.lblVelTitle.setText(QCoreApplication.translate("DataPanel", u"\u7ebf\u901f\u5ea6 (m/s)", None))
        self.valVel.setText(QCoreApplication.translate("DataPanel", u"-", None))
        self.lblAccelTitle.setText(QCoreApplication.translate("DataPanel", u"\u7ebf\u52a0\u901f\u5ea6 (m/s\u00b2)", None))
        self.valAccel.setText(QCoreApplication.translate("DataPanel", u"-", None))
        self.lblOmegaTitle.setText(QCoreApplication.translate("DataPanel", u"\u89d2\u901f\u5ea6 (rad/s)", None))
        self.valOmega.setText(QCoreApplication.translate("DataPanel", u"-", None))
        self.lblRPYTitle.setText(QCoreApplication.translate("DataPanel", u"\u59ff\u6001 RPY (rad)", None))
        self.valRPY.setText(QCoreApplication.translate("DataPanel", u"-", None))
        self.groupJoints.setTitle(QCoreApplication.translate("DataPanel", u"\u5173\u8282\u6570\u636e", None))
        self.groupGRF.setTitle(QCoreApplication.translate("DataPanel", u"\u8db3\u7aef\u63a5\u89e6\u529b (N)", None))
        self.lblGRFLeft.setText(QCoreApplication.translate("DataPanel", u"\u5de6\u811a", None))
        self.valGRFLeft.setText(QCoreApplication.translate("DataPanel", u"-", None))
        self.lblGRFRight.setText(QCoreApplication.translate("DataPanel", u"\u53f3\u811a", None))
        self.valGRFRight.setText(QCoreApplication.translate("DataPanel", u"-", None))
        self.lblGRFFiltered.setText(QCoreApplication.translate("DataPanel", u"\u6ee4\u6ce2\u540e\u5782\u76f4", None))
        self.valGRFFiltered.setText(QCoreApplication.translate("DataPanel", u"-", None))
        pass
    # retranslateUi

