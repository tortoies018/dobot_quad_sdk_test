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
from PySide6.QtWidgets import (QApplication, QGridLayout, QHBoxLayout, QMainWindow,
    QSizePolicy, QStatusBar, QTabWidget, QWidget)

class Ui_MainWindow(object):
    def setupUi(self, MainWindow):
        if not MainWindow.objectName():
            MainWindow.setObjectName(u"MainWindow")
        MainWindow.setMinimumSize(QSize(1400, 900))
        MainWindow.setStyleSheet(u"QMainWindow { background-color: #202225; }")
        self.centralwidget = QWidget(MainWindow)
        self.centralwidget.setObjectName(u"centralwidget")
        self.mainLayout = QHBoxLayout(self.centralwidget)
        self.mainLayout.setObjectName(u"mainLayout")
        self.cameraContainer = QWidget(self.centralwidget)
        self.cameraContainer.setObjectName(u"cameraContainer")
        self.cameraGrid = QGridLayout(self.cameraContainer)
        self.cameraGrid.setSpacing(4)
        self.cameraGrid.setObjectName(u"cameraGrid")

        self.mainLayout.addWidget(self.cameraContainer)

        self.tabWidget = QTabWidget(self.centralwidget)
        self.tabWidget.setObjectName(u"tabWidget")
        self.tabWidget.setStyleSheet(u"QTabWidget::pane { background: #2b2d31; border: 1px solid #42464c; border-top: none; }")
        self.tabWidget.setTabPosition(QTabWidget.North)

        self.mainLayout.addWidget(self.tabWidget)

        self.mainLayout.setStretch(0, 7)
        self.mainLayout.setStretch(1, 3)
        MainWindow.setCentralWidget(self.centralwidget)
        self.statusbar = QStatusBar(MainWindow)
        self.statusbar.setObjectName(u"statusbar")
        self.statusbar.setStyleSheet(u"color: #b8bec4; background: #26292d;")
        MainWindow.setStatusBar(self.statusbar)

        self.retranslateUi(MainWindow)

        QMetaObject.connectSlotsByName(MainWindow)
    # setupUi

    def retranslateUi(self, MainWindow):
        MainWindow.setWindowTitle(QCoreApplication.translate("MainWindow", u"Dobot Quad - \u5168\u6570\u636e\u76d1\u63a7", None))
    # retranslateUi

