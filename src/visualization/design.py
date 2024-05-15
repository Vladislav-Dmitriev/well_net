# -*- coding: utf-8 -*-

import os
import random
import sys

import pandas as pd
from PyQt5 import QtCore, QtGui, QtWidgets
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas, \
    NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure

from src.preparing.preparing_data import get_path


class App(QtWidgets.QMainWindow):

    def __init__(self):
        super().__init__()
        self.left = 400
        self.top = 300
        self.width = 1200
        self.height = 800
        self.main_window()
        self.setMenuWidget(CreateMenu())
        self.show()

    def main_window(self):
        self.setWindowTitle("Module GDIS")
        self.setGeometry(self.left, self.top, self.width, self.height)
        self.setStyleSheet("background-color: lightgray;")
        self.setMenuBar(CreateMenu())
        widget = QtWidgets.QWidget(self)
        self.setCentralWidget(widget)
        hlayout = QtWidgets.QHBoxLayout(widget)
        labels = WidgetLabels(self)
        m = TablePlots()
        hlayout.addWidget(labels, stretch=1)
        hlayout.addWidget(m, stretch=3)


class TablePlots(QtWidgets.QTabWidget):

    def __init__(self):
        QtWidgets.QTabWidget.__init__(self)
        file = pd.ExcelFile(get_path() + '//output//' + 'out_file_geometry.xlsx')
        for name in file.sheet_names[1:-1]:
            self.addTab(WidgetPlot(), name)


class PlotCanvas(FigureCanvas):

    def __init__(self, parent=None, width=5, heigth=4, dpi=100):
        fig = Figure(figsize=(width, heigth), dpi=dpi)
        FigureCanvas.__init__(self, fig)
        self.setParent(parent)
        FigureCanvas.setSizePolicy(self, QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        FigureCanvas.updateGeometry(self)
        self.picture_plot()

    def picture_plot(self):
        data = [random.random() for i in range(250)]
        ax = self.figure.add_subplot(111)
        ax.plot(data, 'r-', linewidth=0.5)
        ax.set_title('PyQt Matplotlib Example')
        self.draw()


class WidgetPlot(QtWidgets.QWidget):

    def __init__(self, *args, **kwargs):
        QtWidgets.QWidget.__init__(self, *args, **kwargs)
        self.setLayout(QtWidgets.QVBoxLayout())
        self.canvas = PlotCanvas(self, width=5, heigth=4, dpi=100)
        self.toolbar = NavigationToolbar(self.canvas)
        button_plot = QtWidgets.QComboBox(self)
        button_plot.addItem('k = 1')
        button_plot.addItem('k = 1.5')
        button_plot.addItem('k = 2')
        button_plot.addItem('k = 2.5')
        button_plot.setFixedSize(200, 25)

        self.layout().addWidget(button_plot)
        self.layout().addWidget(self.toolbar)
        self.layout().addWidget(self.canvas)


class WidgetLabels(QtWidgets.QWidget):

    def __init__(self, *args, **kwargs):
        QtWidgets.QWidget.__init__(self, *args, **kwargs)
        self.param_labels()

    def param_labels(self):
        # главный виджет со всеми окнами задания параметров расчета
        main_box = QtWidgets.QVBoxLayout(self)

        # горизонтальный виджет для задания имени файла/пути
        box_data = QtWidgets.QHBoxLayout(self)
        filepath = QtWidgets.QLineEdit()
        file_button = QtWidgets.QPushButton("...")
        file_button.clicked.connect(
            lambda: filepath.setText(QtWidgets.QFileDialog.getOpenFileName(self, filter='*.csv *.xlsx')[0]))
        file_button.setFixedSize(30, 25)
        box_data.addWidget(QtWidgets.QLabel('Данные:'))
        box_data.addWidget(filepath)
        box_data.addWidget(file_button)

        # горизонтальный виджет для ввода даты ГДИС
        box_gdis_date = QtWidgets.QHBoxLayout(self)
        box_gdis_date.addWidget(QtWidgets.QLabel('Дата ГДИС:'))
        box_gdis_date.addWidget(QtWidgets.QLineEdit())

        # горизонтальный виджет для рапределения ГДИС по годам
        box_gdis_opt = QtWidgets.QHBoxLayout(self)
        box_gdis_opt.addWidget(QtWidgets.QLabel('ГДИС по годам:'))
        box_gdis_opt.addWidget(QtWidgets.QLineEdit())

        # горизонтальный виджет для выбора критерия охвата скважин исследованиями
        box_criteria = QtWidgets.QHBoxLayout(self)
        edit_criteria = QtWidgets.QComboBox()
        edit_criteria.addItem('True')
        edit_criteria.addItem('False')
        edit_criteria.setFixedSize(155, 25)
        box_criteria.addWidget(QtWidgets.QLabel('Критерий охвата:'))
        box_criteria.addWidget(edit_criteria)

        # горизонтальный виджет для ввода максимального радиуса исследования
        box_max_r = QtWidgets.QHBoxLayout(self)
        box_max_r.addWidget(QtWidgets.QLabel('Максимальный R:'))
        box_max_r.addWidget(QtWidgets.QLineEdit())

        # горизонтальный виджет для ввода начального коэффициента увеличения радиуса
        box_min_coef = QtWidgets.QHBoxLayout(self)
        box_min_coef.addWidget(QtWidgets.QLabel('Минимальный коэф-т:'))
        box_min_coef.addWidget(QtWidgets.QLineEdit())

        # горизонтальный виджет для ввода начального коэффициента увеличения радиуса
        box_max_coef = QtWidgets.QHBoxLayout(self)
        box_max_coef.addWidget(QtWidgets.QLabel('Максимальный коэф-т:'))
        box_max_coef.addWidget(QtWidgets.QLineEdit())

        # горизонтальный виджет для ввода шага коэффициента кратного увеличения радиуса
        box_step_coef = QtWidgets.QHBoxLayout(self)
        box_step_coef.addWidget(QtWidgets.QLabel('Шаг коэф-та:'))
        box_step_coef.addWidget(QtWidgets.QLineEdit())

        # добавление всех виджетов в главный виджет
        main_box.addLayout(box_data)
        main_box.addLayout(box_gdis_date)
        main_box.addLayout(box_gdis_opt)
        main_box.addLayout(box_criteria)
        main_box.addLayout(box_max_r)
        main_box.addLayout(box_min_coef)
        main_box.addLayout(box_max_coef)
        main_box.addLayout(box_step_coef)

        main_box.setAlignment(QtCore.Qt.AlignTop)


class CreateMenu(QtWidgets.QMenuBar):

    def __init__(self):
        QtWidgets.QMenuBar.__init__(self)
        self.create_menu_bar()
        self.createActions()

    def create_menu_bar(self):
        fileMenu = QtWidgets.QMenu("&File", self)
        newAction = QtWidgets.QAction("&New", self)
        newAction.setShortcut('Ctrl+N')
        newAction.setIcon(QtGui.QIcon(":file-new.svg"))
        openAction = QtWidgets.QAction(QtGui.QIcon(":file-open.svg"), "&Open...", self)
        saveAction = QtWidgets.QAction(QtGui.QIcon(":file-save.svg"), "&Save", self)
        exitAction = QtWidgets.QAction("&Exit", self)
        exitAction.setShortcut('Ctrl+Q')
        exitAction.triggered.connect(lambda: QtWidgets.QApplication.quit())
        fileMenu.addAction(newAction)
        fileMenu.addAction(openAction)
        fileMenu.addAction(saveAction)
        fileMenu.addAction(exitAction)
        self.addMenu(fileMenu)

        editMenu = QtWidgets.QMenu("&Edit", self)
        copyAction = QtWidgets.QAction(QtGui.QIcon(":edit-copy.svg"), "&Copy", self)
        pasteAction = QtWidgets.QAction(QtGui.QIcon(":edit-paste.svg"), "&Paste", self)
        cutAction = QtWidgets.QAction(QtGui.QIcon(":edit-cut.svg"), "&Cut", self)
        editMenu.addAction(copyAction)
        editMenu.addAction(pasteAction)
        editMenu.addAction(cutAction)
        self.addMenu(editMenu)

        helpMenu = QtWidgets.QMenu("&Help", self)
        referenceAction = QtWidgets.QAction("&Reference", self)
        referenceAction.triggered.connect(lambda: os.startfile(str(get_path() + '/README.txt')))
        helpMenu.addAction(referenceAction)
        self.addMenu(helpMenu)

    def createActions(self):
        # download action

        download = QtWidgets.QAction("&Open...", self)
        # self.download.triggered.connect(lambda: QApplication.quit())
        # File actions
        newAction = QtWidgets.QAction("&New", self)
        newAction.setShortcut('Ctrl+N')
        newAction.setIcon(QtGui.QIcon(":file-new.svg"))
        # self.newAction.triggered.connect(lambda: QFileDialog.getOpenFileName())
        openAction = QtWidgets.QAction(QtGui.QIcon(":file-open.svg"), "&Open...", self)
        saveAction = QtWidgets.QAction(QtGui.QIcon(":file-save.svg"), "&Save", self)
        exitAction = QtWidgets.QAction("&Exit", self)
        exitAction.setShortcut('Ctrl+Q')
        exitAction.triggered.connect(lambda: QtWidgets.QApplication.quit())
        # Edit actions
        copyAction = QtWidgets.QAction(QtGui.QIcon(":edit-copy.svg"), "&Copy", self)
        pasteAction = QtWidgets.QAction(QtGui.QIcon(":edit-paste.svg"), "&Paste", self)
        cutAction = QtWidgets.QAction(QtGui.QIcon(":edit-cut.svg"), "&Cut", self)
        # Help actions
        referenceAction = QtWidgets.QAction("&Reference", self)
        referenceAction.triggered.connect(lambda: os.startfile(str(get_path() + '/README.txt')))


if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    ex = App()
    sys.exit(app.exec_())
