import os
import sys

import matplotlib

matplotlib.use('Qt5Agg')
from matplotlib.backends.backend_qt5agg import FigureCanvasAgg as FigureCanvas, \
    NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure
from PyQt5.QtGui import *
from PyQt5.QtWidgets import *

from src.calculation.auxiliary_functions import get_path


class MyCanvas(FigureCanvas):

    def __init__(self, parent=None, width=5, height=4, dpi=100):
        fig = Figure(figsize=(width, height), dpi=dpi)
        self.axes = fig.add_subplot(111)
        self.axes.plot([1, 4, 5], [2, 0, 7])
        super(MyCanvas, self).__init__(fig)


class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()

        # Настройки окна
        self.setWindowTitle('Опорная сеть')
        self.setGeometry(500, 200, 1000, 700)
        self.createActions()
        self.create_menu_bar()
        self.btns()
        self.createActions()
        self.sc = MyCanvas(self, width=5, height=4, dpi=100)
        self.toolbar = NavigationToolbar(self.sc)
        self.layout = QVBoxLayout()
        self.layout.addWidget(self.toolbar)
        self.layout.addWidget(self.sc)
        # widget = QWidget()
        # widget.setLayout(self.layout)
        self.show()

    def create_menu_bar(self):
        menuBar = self.menuBar()
        # Creating menu using a QMenu object
        fileMenu = QMenu("&File", self)
        menuBar.addMenu(fileMenu)
        fileMenu.addAction(self.newAction)
        fileMenu.addAction(self.openAction)
        fileMenu.addAction(self.saveAction)
        fileMenu.addAction(self.exitAction)
        # Creating menu using a title
        editMenu = menuBar.addMenu("&Edit")
        editMenu.addAction(self.copyAction)
        editMenu.addAction(self.pasteAction)
        editMenu.addAction(self.cutAction)

        helpMenu = menuBar.addMenu("&Help")
        helpMenu.addAction(self.referenceAction)

    def btns(self):
        # текст файла с данными
        text_file = QLabel('Данные:', self)
        # text_file.setStyleSheet('font-size: 14px')
        text_file.move(10, 32)
        text_file.setFixedSize(110, 20)
        # Окно вывода пути к файлу с данными
        layout = QLineEdit(self)
        layout.setFixedSize(150, 20)
        layout.setStyleSheet("background-color: white; border: 1px solid black")
        layout.move(120, 30)
        # Кнопка загрузки пути к файлу со скважинами
        download_data = QPushButton('...', self)
        download_data.setFixedSize(20, 21)
        download_data.move(270, 30)
        download_data.clicked.connect(
            lambda: layout.setText(QFileDialog.getOpenFileName(self, filter='*.csv *.xlsx')[0]))
        self.data_path = download_data.text()

        # текст даты последнего ГДИС
        text_gdis_date = QLabel('Дата ГДИС:', self)
        text_gdis_date.move(10, 104)
        # Окно для ввода даты последнего ГДИС
        layout_gdis_date = QLineEdit(self)
        layout_gdis_date.setFixedSize(150, 20)
        layout_gdis_date.setStyleSheet("background-color: white; border: 1px solid black")
        layout_gdis_date.move(120, 110)

        # текст gdis_option
        text_gdis_opt = QLabel('ГДИС по годам:', self)
        # text_gdis_opt.setStyleSheet('font-size: 14px')
        text_gdis_opt.setFixedSize(250, 16)
        text_gdis_opt.move(10, 130)
        text_gdis_opt.setFixedSize(210, 20)
        # Окно ввода кол-ва лет доп. исследований ГДИС
        layout_gdis_opt = QComboBox(self)
        layout_gdis_opt.addItem('нет')
        layout_gdis_opt.addItem('1')
        layout_gdis_opt.addItem('2')
        layout_gdis_opt.setFixedSize(150, 20)
        layout_gdis_opt.move(120, 130)

        # текст опции охвата траектории скважины (процент охвата траектории или охват при попадании любой точки)
        text_include = QLabel('Критерий охвата:', self)
        text_include.move(10, 146)
        text_gdis_opt.setFixedSize(210, 20)
        # Окно ввода критерия охвата скважин
        layout_gdis_opt = QComboBox(self)
        layout_gdis_opt.addItem('True')
        layout_gdis_opt.addItem('False')
        layout_gdis_opt.setFixedSize(150, 20)
        layout_gdis_opt.move(120, 151)

        # текст ограничения оптимального радиуса исследования
        text_limit_radius = QLabel('Максимальный R:', self)
        text_limit_radius.move(10, 171)
        text_limit_radius.setFixedSize(110, 20)
        # Окно для ввода ограничения оптимального радиуса исследования
        layout_limit_radius = QLineEdit(self)
        layout_limit_radius.setFixedSize(150, 20)
        layout_limit_radius.setStyleSheet("background-color: white; border: 1px solid black")
        layout_limit_radius.move(120, 171)

        # текст mult_coef
        text_mult = QLabel('Коэф-ты для R:', self)
        # text_mult.setStyleSheet('font-size: 14px')
        text_mult.move(10, 211)
        text_mult.setFixedSize(110, 20)
        # Окно ввода списка коэффициентов для увеличения радиуса исследования
        layout_pvt = QLineEdit(self)
        layout_pvt.setFixedSize(150, 20)
        layout_pvt.setStyleSheet("background-color: white; border: 1px solid black")
        layout_pvt.move(120, 211)
        # layout_pvt.setText(' ,'.join(str(layout_pvt.text()).split(',')))

    def createActions(self):
        # download action

        self.download = QAction("&Open...", self)
        # self.download.triggered.connect(lambda: QApplication.quit())
        # File actions
        self.newAction = QAction("&New", self)
        self.newAction.setShortcut('Ctrl+N')
        self.newAction.setIcon(QIcon(":file-new.svg"))
        # self.newAction.triggered.connect(lambda: QFileDialog.getOpenFileName())
        self.openAction = QAction(QIcon(":file-open.svg"), "&Open...", self)
        self.saveAction = QAction(QIcon(":file-save.svg"), "&Save", self)
        self.exitAction = QAction("&Exit", self)
        self.exitAction.setShortcut('Ctrl+Q')
        self.exitAction.triggered.connect(lambda: QApplication.quit())
        # Edit actions
        self.copyAction = QAction(QIcon(":edit-copy.svg"), "&Copy", self)
        self.pasteAction = QAction(QIcon(":edit-paste.svg"), "&Paste", self)
        self.cutAction = QAction(QIcon(":edit-cut.svg"), "&Cut", self)
        # Help actions
        self.referenceAction = QAction("&Reference", self)
        self.referenceAction.triggered.connect(lambda: os.startfile(str(get_path() + '/README.txt')))


app = QApplication(sys.argv)
window = MainWindow()
window.show()
app.exec()
