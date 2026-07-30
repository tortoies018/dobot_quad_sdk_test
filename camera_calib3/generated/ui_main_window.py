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
from PySide6.QtWidgets import (QApplication, QGroupBox, QHBoxLayout, QLabel,
    QMainWindow, QPushButton, QSizePolicy, QStatusBar,
    QVBoxLayout, QWidget)

class Ui_MainWindow(object):
    def setupUi(self, MainWindow):
        if not MainWindow.objectName():
            MainWindow.setObjectName(u"MainWindow")
        MainWindow.setMinimumSize(QSize(1400, 850))
        MainWindow.setStyleSheet(u"QMainWindow { background-color: #1e1e1e; }")
        self.centralwidget = QWidget(MainWindow)
        self.centralwidget.setObjectName(u"centralwidget")
        self.mainLayout = QHBoxLayout(self.centralwidget)
        self.mainLayout.setObjectName(u"mainLayout")
        self.panelFront = QWidget(self.centralwidget)
        self.panelFront.setObjectName(u"panelFront")
        self.layoutFront = QVBoxLayout(self.panelFront)
        self.layoutFront.setObjectName(u"layoutFront")
        self.titleFront = QLabel(self.panelFront)
        self.titleFront.setObjectName(u"titleFront")
        self.titleFront.setAlignment(Qt.AlignCenter)
        self.titleFront.setStyleSheet(u"font: bold 16px; color: #0af; padding: 6px; background: #252525; border-radius: 4px;")

        self.layoutFront.addWidget(self.titleFront)

        self.viewFront = QLabel(self.panelFront)
        self.viewFront.setObjectName(u"viewFront")
        self.viewFront.setAlignment(Qt.AlignCenter)
        self.viewFront.setMinimumSize(QSize(480, 360))
        self.viewFront.setStyleSheet(u"background-color: #111; color: #555; font: 18px; border: 1px solid #333; border-radius: 2px;")

        self.layoutFront.addWidget(self.viewFront)

        self.ctrlFront = QHBoxLayout()
        self.ctrlFront.setObjectName(u"ctrlFront")
        self.btnCapFront = QPushButton(self.panelFront)
        self.btnCapFront.setObjectName(u"btnCapFront")
        self.btnCapFront.setStyleSheet(u"QPushButton { background:#0af; color:#fff; font:13px; padding:8px 20px; border-radius:4px; } QPushButton:hover { background:#0cf; } QPushButton:disabled { background:#555; }")

        self.ctrlFront.addWidget(self.btnCapFront)

        self.btnCalFront = QPushButton(self.panelFront)
        self.btnCalFront.setObjectName(u"btnCalFront")
        self.btnCalFront.setStyleSheet(u"QPushButton { background:#0a0; color:#fff; font:13px; padding:8px 20px; border-radius:4px; } QPushButton:hover { background:#0c0; } QPushButton:disabled { background:#555; }")
        self.btnCalFront.setEnabled(False)

        self.ctrlFront.addWidget(self.btnCalFront)

        self.btnResetFront = QPushButton(self.panelFront)
        self.btnResetFront.setObjectName(u"btnResetFront")
        self.btnResetFront.setStyleSheet(u"QPushButton { background:#a33; color:#fff; font:13px; padding:8px 20px; border-radius:4px; } QPushButton:hover { background:#c55; }")

        self.ctrlFront.addWidget(self.btnResetFront)


        self.layoutFront.addLayout(self.ctrlFront)

        self.infoFront = QLabel(self.panelFront)
        self.infoFront.setObjectName(u"infoFront")
        self.infoFront.setStyleSheet(u"color: #aaa; font: 12px; padding: 2px;")

        self.layoutFront.addWidget(self.infoFront)

        self.countFront = QLabel(self.panelFront)
        self.countFront.setObjectName(u"countFront")
        self.countFront.setStyleSheet(u"color: #fa0; font: 12px; padding: 2px;")

        self.layoutFront.addWidget(self.countFront)

        self.resultFront = QGroupBox(self.panelFront)
        self.resultFront.setObjectName(u"resultFront")
        self.resultFront.setStyleSheet(u"QGroupBox { font: bold 13px; color: #0f0; border: 1px solid #333; border-radius: 4px; margin-top: 8px; padding: 12px 6px 6px 6px; background: #252525; } QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 4px; }")
        self.resultLayoutFront = QVBoxLayout(self.resultFront)
        self.resultLayoutFront.setObjectName(u"resultLayoutFront")
        self.textResultFront = QLabel(self.resultFront)
        self.textResultFront.setObjectName(u"textResultFront")
        self.textResultFront.setStyleSheet(u"color: #aaa; font: 11px monospace; padding: 2px;")
        self.textResultFront.setTextInteractionFlags(Qt.TextSelectableByMouse)

        self.resultLayoutFront.addWidget(self.textResultFront)


        self.layoutFront.addWidget(self.resultFront)


        self.mainLayout.addWidget(self.panelFront)

        self.panelRear = QWidget(self.centralwidget)
        self.panelRear.setObjectName(u"panelRear")
        self.layoutRear = QVBoxLayout(self.panelRear)
        self.layoutRear.setObjectName(u"layoutRear")
        self.titleRear = QLabel(self.panelRear)
        self.titleRear.setObjectName(u"titleRear")
        self.titleRear.setAlignment(Qt.AlignCenter)
        self.titleRear.setStyleSheet(u"font: bold 16px; color: #f0a; padding: 6px; background: #252525; border-radius: 4px;")

        self.layoutRear.addWidget(self.titleRear)

        self.viewRear = QLabel(self.panelRear)
        self.viewRear.setObjectName(u"viewRear")
        self.viewRear.setAlignment(Qt.AlignCenter)
        self.viewRear.setMinimumSize(QSize(480, 360))
        self.viewRear.setStyleSheet(u"background-color: #111; color: #555; font: 18px; border: 1px solid #333; border-radius: 2px;")

        self.layoutRear.addWidget(self.viewRear)

        self.ctrlRear = QHBoxLayout()
        self.ctrlRear.setObjectName(u"ctrlRear")
        self.btnCapRear = QPushButton(self.panelRear)
        self.btnCapRear.setObjectName(u"btnCapRear")
        self.btnCapRear.setStyleSheet(u"QPushButton { background:#0af; color:#fff; font:13px; padding:8px 20px; border-radius:4px; } QPushButton:hover { background:#0cf; } QPushButton:disabled { background:#555; }")

        self.ctrlRear.addWidget(self.btnCapRear)

        self.btnCalRear = QPushButton(self.panelRear)
        self.btnCalRear.setObjectName(u"btnCalRear")
        self.btnCalRear.setStyleSheet(u"QPushButton { background:#0a0; color:#fff; font:13px; padding:8px 20px; border-radius:4px; } QPushButton:hover { background:#0c0; } QPushButton:disabled { background:#555; }")
        self.btnCalRear.setEnabled(False)

        self.ctrlRear.addWidget(self.btnCalRear)

        self.btnResetRear = QPushButton(self.panelRear)
        self.btnResetRear.setObjectName(u"btnResetRear")
        self.btnResetRear.setStyleSheet(u"QPushButton { background:#a33; color:#fff; font:13px; padding:8px 20px; border-radius:4px; } QPushButton:hover { background:#c55; }")

        self.ctrlRear.addWidget(self.btnResetRear)


        self.layoutRear.addLayout(self.ctrlRear)

        self.infoRear = QLabel(self.panelRear)
        self.infoRear.setObjectName(u"infoRear")
        self.infoRear.setStyleSheet(u"color: #aaa; font: 12px; padding: 2px;")

        self.layoutRear.addWidget(self.infoRear)

        self.countRear = QLabel(self.panelRear)
        self.countRear.setObjectName(u"countRear")
        self.countRear.setStyleSheet(u"color: #fa0; font: 12px; padding: 2px;")

        self.layoutRear.addWidget(self.countRear)

        self.resultRear = QGroupBox(self.panelRear)
        self.resultRear.setObjectName(u"resultRear")
        self.resultRear.setStyleSheet(u"QGroupBox { font: bold 13px; color: #0f0; border: 1px solid #333; border-radius: 4px; margin-top: 8px; padding: 12px 6px 6px 6px; background: #252525; } QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 4px; }")
        self.resultLayoutRear = QVBoxLayout(self.resultRear)
        self.resultLayoutRear.setObjectName(u"resultLayoutRear")
        self.textResultRear = QLabel(self.resultRear)
        self.textResultRear.setObjectName(u"textResultRear")
        self.textResultRear.setStyleSheet(u"color: #aaa; font: 11px monospace; padding: 2px;")
        self.textResultRear.setTextInteractionFlags(Qt.TextSelectableByMouse)

        self.resultLayoutRear.addWidget(self.textResultRear)


        self.layoutRear.addWidget(self.resultRear)


        self.mainLayout.addWidget(self.panelRear)

        self.mainLayout.setStretch(0, 1)
        self.mainLayout.setStretch(1, 1)
        MainWindow.setCentralWidget(self.centralwidget)
        self.statusbar = QStatusBar(MainWindow)
        self.statusbar.setObjectName(u"statusbar")
        self.statusbar.setStyleSheet(u"color: #aaa; background: #333; font: 12px;")
        MainWindow.setStatusBar(self.statusbar)

        self.retranslateUi(MainWindow)

        QMetaObject.connectSlotsByName(MainWindow)
    # setupUi

    def retranslateUi(self, MainWindow):
        MainWindow.setWindowTitle(QCoreApplication.translate("MainWindow", u"Dobot Quad \u53cc\u76f8\u673a\u6807\u5b9a", None))
        self.titleFront.setText(QCoreApplication.translate("MainWindow", u"\u524d\u7f6e RGB (camera2)", None))
        self.viewFront.setText(QCoreApplication.translate("MainWindow", u"\u7b49\u5f85\u76f8\u673a...", None))
        self.btnCapFront.setText(QCoreApplication.translate("MainWindow", u"\u6355\u83b7\u5e27", None))
        self.btnCalFront.setText(QCoreApplication.translate("MainWindow", u"\u6807\u5b9a", None))
        self.btnResetFront.setText(QCoreApplication.translate("MainWindow", u"\u91cd\u7f6e", None))
        self.infoFront.setText(QCoreApplication.translate("MainWindow", u"\u68c0\u6d4b\u7ed3\u679c: \u2014", None))
        self.countFront.setText(QCoreApplication.translate("MainWindow", u"\u5df2\u6355\u83b7: 0 \u5e27", None))
        self.resultFront.setTitle(QCoreApplication.translate("MainWindow", u"\u6807\u5b9a\u7ed3\u679c", None))
        self.textResultFront.setText(QCoreApplication.translate("MainWindow", u"\u7b49\u5f85\u6807\u5b9a...", None))
        self.titleRear.setText(QCoreApplication.translate("MainWindow", u"\u540e\u7f6e RGB (camera3)", None))
        self.viewRear.setText(QCoreApplication.translate("MainWindow", u"\u7b49\u5f85\u76f8\u673a...", None))
        self.btnCapRear.setText(QCoreApplication.translate("MainWindow", u"\u6355\u83b7\u5e27", None))
        self.btnCalRear.setText(QCoreApplication.translate("MainWindow", u"\u6807\u5b9a", None))
        self.btnResetRear.setText(QCoreApplication.translate("MainWindow", u"\u91cd\u7f6e", None))
        self.infoRear.setText(QCoreApplication.translate("MainWindow", u"\u68c0\u6d4b\u7ed3\u679c: \u2014", None))
        self.countRear.setText(QCoreApplication.translate("MainWindow", u"\u5df2\u6355\u83b7: 0 \u5e27", None))
        self.resultRear.setTitle(QCoreApplication.translate("MainWindow", u"\u6807\u5b9a\u7ed3\u679c", None))
        self.textResultRear.setText(QCoreApplication.translate("MainWindow", u"\u7b49\u5f85\u6807\u5b9a...", None))
    # retranslateUi

