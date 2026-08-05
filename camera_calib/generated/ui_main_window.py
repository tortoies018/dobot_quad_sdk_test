# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'main_window.ui'
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
from PySide6.QtWidgets import (QApplication, QComboBox, QGroupBox, QHBoxLayout,
    QLabel, QListWidget, QListWidgetItem, QMainWindow,
    QPushButton, QSizePolicy, QSpacerItem, QStatusBar,
    QVBoxLayout, QWidget)

class Ui_MainWindow(object):
    def setupUi(self, MainWindow):
        if not MainWindow.objectName():
            MainWindow.setObjectName(u"MainWindow")
        MainWindow.setMinimumSize(QSize(1200, 800))
        MainWindow.setStyleSheet(u"QMainWindow { background-color: #202225; }")
        self.centralwidget = QWidget(MainWindow)
        self.centralwidget.setObjectName(u"centralwidget")
        self.mainLayout = QHBoxLayout(self.centralwidget)
        self.mainLayout.setObjectName(u"mainLayout")
        self.leftPanel = QWidget(self.centralwidget)
        self.leftPanel.setObjectName(u"leftPanel")
        self.leftLayout = QVBoxLayout(self.leftPanel)
        self.leftLayout.setObjectName(u"leftLayout")
        self.comboCamera = QComboBox(self.leftPanel)
        self.comboCamera.addItem("")
        self.comboCamera.addItem("")
        self.comboCamera.setObjectName(u"comboCamera")
        self.comboCamera.setStyleSheet(u"QComboBox { background: #26292d; color: #fff; padding: 6px; font: 13px; border: 1px solid #55585e; border-radius: 4px; }\n"
"QComboBox::drop-down { border: none; }\n"
"QComboBox QAbstractItemView { background:#2b2d31; color:#f5f5f5; border:1px solid #55585e; outline:none; selection-background-color:#29b6f6; selection-color:#fff; }\n"
"QComboBox QAbstractItemView::item { padding:6px 8px; }\n"
"QComboBox QAbstractItemView::item:hover { background:#3a3d42; }")

        self.leftLayout.addWidget(self.comboCamera)

        self.labelCameraView = QLabel(self.leftPanel)
        self.labelCameraView.setObjectName(u"labelCameraView")
        self.labelCameraView.setAlignment(Qt.AlignCenter)
        self.labelCameraView.setMinimumSize(QSize(480, 360))
        self.labelCameraView.setStyleSheet(u"background-color: #16181c; color: #a8b3bc; font: 16px; border: 1px solid #42464c; border-radius: 2px; padding: 0px;")

        self.leftLayout.addWidget(self.labelCameraView)

        self.labelDetectResult = QLabel(self.leftPanel)
        self.labelDetectResult.setObjectName(u"labelDetectResult")
        self.labelDetectResult.setMinimumSize(QSize(0, 0))
        self.labelDetectResult.setStyleSheet(u"background-color: #16181c; color: #b8bec4; font: 12px; border: 1px solid #42464c; padding: 4px;")

        self.leftLayout.addWidget(self.labelDetectResult)


        self.mainLayout.addWidget(self.leftPanel)

        self.rightPanel = QWidget(self.centralwidget)
        self.rightPanel.setObjectName(u"rightPanel")
        self.rightLayout = QVBoxLayout(self.rightPanel)
        self.rightLayout.setObjectName(u"rightLayout")
        self.groupControl = QGroupBox(self.rightPanel)
        self.groupControl.setObjectName(u"groupControl")
        self.groupControl.setStyleSheet(u"QGroupBox { font: bold 14px; color: #4fc3f7; border: 1px solid #42464c; border-radius: 6px; margin-top: 12px; padding: 16px 8px 8px 8px; background: #2b2d31; }\n"
"QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 6px; }\n"
"QPushButton { font: 13px; padding: 8px 16px; border-radius: 4px; min-height: 36px; }")
        self.controlLayout = QHBoxLayout(self.groupControl)
        self.controlLayout.setObjectName(u"controlLayout")
        self.btnCapture = QPushButton(self.groupControl)
        self.btnCapture.setObjectName(u"btnCapture")
        self.btnCapture.setStyleSheet(u"QPushButton { background: #29b6f6; color: #fff; } QPushButton:hover { background: #4fc3f7; } QPushButton:disabled { background: #4a4d52; color:#9a9da2; }")

        self.controlLayout.addWidget(self.btnCapture)

        self.btnCalibrate = QPushButton(self.groupControl)
        self.btnCalibrate.setObjectName(u"btnCalibrate")
        self.btnCalibrate.setStyleSheet(u"QPushButton { background: #2e7d32; color: #fff; } QPushButton:hover { background: #43a047; } QPushButton:disabled { background: #4a4d52; color:#9a9da2; }")

        self.controlLayout.addWidget(self.btnCalibrate)

        self.btnReset = QPushButton(self.groupControl)
        self.btnReset.setObjectName(u"btnReset")
        self.btnReset.setStyleSheet(u"QPushButton { background: #c62828; color: #fff; } QPushButton:hover { background: #e53935; }")

        self.controlLayout.addWidget(self.btnReset)


        self.rightLayout.addWidget(self.groupControl)

        self.groupFrames = QGroupBox(self.rightPanel)
        self.groupFrames.setObjectName(u"groupFrames")
        self.groupFrames.setStyleSheet(u"QGroupBox { font: bold 14px; color: #ffb74d; border: 1px solid #42464c; border-radius: 6px; margin-top: 12px; padding: 16px 8px 8px 8px; background: #2b2d31; }\n"
"QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 6px; }")
        self.framesLayout = QVBoxLayout(self.groupFrames)
        self.framesLayout.setObjectName(u"framesLayout")
        self.listFrames = QListWidget(self.groupFrames)
        self.listFrames.setObjectName(u"listFrames")
        self.listFrames.setStyleSheet(u"QListWidget { background: #1a1d21; color: #e0e0e0; font: 12px; border: 1px solid #42464c; border-radius: 2px; }\n"
"QListWidget::item { padding: 4px; } QListWidget::item:selected { background: #29b6f6; color: #fff; }")

        self.framesLayout.addWidget(self.listFrames)


        self.rightLayout.addWidget(self.groupFrames)

        self.groupResult = QGroupBox(self.rightPanel)
        self.groupResult.setObjectName(u"groupResult")
        self.groupResult.setStyleSheet(u"QGroupBox { font: bold 14px; color: #69f0ae; border: 1px solid #42464c; border-radius: 6px; margin-top: 12px; padding: 16px 8px 8px 8px; background: #2b2d31; }\n"
"QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 6px; }")
        self.resultLayout = QVBoxLayout(self.groupResult)
        self.resultLayout.setObjectName(u"resultLayout")
        self.labelResult = QLabel(self.groupResult)
        self.labelResult.setObjectName(u"labelResult")
        self.labelResult.setStyleSheet(u"color: #b8bec4; font: 11px monospace; padding: 4px;")
        self.labelResult.setTextInteractionFlags(Qt.TextSelectableByMouse)

        self.resultLayout.addWidget(self.labelResult)


        self.rightLayout.addWidget(self.groupResult)

        self.verticalSpacer = QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)

        self.rightLayout.addItem(self.verticalSpacer)


        self.mainLayout.addWidget(self.rightPanel)

        self.mainLayout.setStretch(0, 6)
        self.mainLayout.setStretch(1, 4)
        MainWindow.setCentralWidget(self.centralwidget)
        self.statusbar = QStatusBar(MainWindow)
        self.statusbar.setObjectName(u"statusbar")
        self.statusbar.setStyleSheet(u"color: #b8bec4; background: #26292d; font: 12px;")
        MainWindow.setStatusBar(self.statusbar)

        self.retranslateUi(MainWindow)

        QMetaObject.connectSlotsByName(MainWindow)
    # setupUi

    def retranslateUi(self, MainWindow):
        MainWindow.setWindowTitle(QCoreApplication.translate("MainWindow", u"Dobot Quad \u76f8\u673a\u6807\u5b9a", None))
        self.comboCamera.setItemText(0, QCoreApplication.translate("MainWindow", u"\u524d\u7f6e RGB camera2", None))
        self.comboCamera.setItemText(1, QCoreApplication.translate("MainWindow", u"\u540e\u7f6e RGB camera3", None))

        self.labelCameraView.setText(QCoreApplication.translate("MainWindow", u"\u7b49\u5f85\u76f8\u673a\u753b\u9762...", None))
        self.labelDetectResult.setText(QCoreApplication.translate("MainWindow", u"\u68c0\u6d4b\u7ed3\u679c", None))
        self.groupControl.setTitle(QCoreApplication.translate("MainWindow", u"\u63a7\u5236", None))
        self.btnCapture.setText(QCoreApplication.translate("MainWindow", u"\u6355\u83b7\u5e27", None))
        self.btnCalibrate.setText(QCoreApplication.translate("MainWindow", u"\u6807\u5b9a", None))
        self.btnReset.setText(QCoreApplication.translate("MainWindow", u"\u91cd\u7f6e", None))
        self.groupFrames.setTitle(QCoreApplication.translate("MainWindow", u"\u5df2\u6355\u83b7\u5e27", None))
        self.groupResult.setTitle(QCoreApplication.translate("MainWindow", u"\u6807\u5b9a\u7ed3\u679c", None))
        self.labelResult.setText(QCoreApplication.translate("MainWindow", u"\u7b49\u5f85\u6807\u5b9a...", None))
    # retranslateUi

