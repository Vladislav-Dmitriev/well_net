import os
import sys

import matplotlib
import numpy as np

matplotlib.use('Qt5Agg')
from matplotlib.backends.backend_qt5agg import FigureCanvasAgg as FigureCanvas, \
    NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure
from functions import get_path
# from main import func_main
from PyQt5.QtCore import *
from PyQt5.QtGui import *
from PyQt5.QtWidgets import *


class MainWindow(QMainWindow):

    def __init__(self):
        super(MainWindow, self).__init__()

        # Настройки окна
        self.setWindowTitle('Опорная сеть')
        self.setGeometry(0, 0, 1920, 1080)
        self.createActions()
        self.create_menu_bar()
        # self.image_viewer()
        # self.plot_image()
        self.btns()
        self.createActions()

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

        # текст ГДИС
        text_gdis = QLabel('ГДИС:', self)
        # text_gdis.setStyleSheet('font-size: 14px')
        text_gdis.move(10, 51)
        text_gdis.setFixedSize(110, 20)
        # Окно вывода пути к файлу ГДИС
        layout_gdis = QLineEdit(self)
        layout_gdis.setFixedSize(150, 20)
        layout_gdis.setStyleSheet("background-color: white; border: 1px solid black")
        layout_gdis.move(120, 50)
        # Кнопка загрузки пути к файлу с ГДИСами
        download_gdis = QPushButton('...', self)
        download_gdis.setFixedSize(20, 21)
        download_gdis.move(270, 50)
        download_gdis.clicked.connect(
            lambda: layout_gdis.setText(QFileDialog.getOpenFileName(self, filter='*.csv *.xlsx')[0]))
        self.gdis_path = download_gdis.text()

        # текст исключения
        text_exception = QLabel('Исключения:', self)
        # text_exception.setStyleSheet('font-size: 14px')
        text_exception.move(10, 70)
        text_exception.setFixedSize(110, 20)
        # Окно вывода пути к файлу с исключаемыми скважинами
        layout_exception = QLineEdit(self)
        layout_exception.setFixedSize(150, 20)
        layout_exception.setStyleSheet("background-color: white; border: 1px solid black")
        layout_exception.move(120, 70)
        # Кнопка загрузки пути к файлу с исключаемыми скважинами
        download_exception = QPushButton('...', self)
        download_exception.setFixedSize(20, 21)
        download_exception.move(270, 70)
        download_exception.clicked.connect(
            lambda: layout_exception.setText(QFileDialog.getOpenFileName(self, filter='*.csv *.xlsx')[0]))
        self.exception_path = download_exception.text()

        # текст PVT
        text_pvt = QLabel('PVT:', self)
        # text_pvt.setStyleSheet('font-size: 14px')
        text_pvt.move(10, 89)
        text_pvt.setFixedSize(110, 20)
        # Окно вывода пути к справочнику PVT
        layout_pvt = QLineEdit(self)
        layout_pvt.setFixedSize(150, 20)
        layout_pvt.setStyleSheet("background-color: white; border: 1px solid black")
        layout_pvt.move(120, 90)
        # Кнопка загрузки пути к справочнику PVT
        download_pvt = QPushButton('...', self)
        download_pvt.setFixedSize(20, 21)
        download_pvt.move(270, 90)
        download_pvt.clicked.connect(
            lambda: layout_exception.setText(QFileDialog.getOpenFileName(self, filter='*.csv *.xlsx')[0]))

        # текст даты последнего ГДИС
        text_gdis_date = QLabel('Дата ГДИС:', self)
        text_gdis_date.move(10, 104)
        text_pvt.setFixedSize(110, 20)
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

        # Кнопка запуска расчета
        calc_button = QPushButton('Расчет', self)
        # calc_button.setStyleSheet()
        # calc_button.setFixedSize(100, 20)
        calc_button.move(10, 600)
        # calc_button.clicked.connect(lambda: self.run_main_func())

    # def run_main_func(self):
    #     if __name__ == '__main__':
    #         func_main()

    def image_viewer(self):

        # Create a QLabel for displaying images
        self.image_label = QLabel(self)
        self.image_label.setGeometry(400, 15, 650, 650)
        self.image_label.setScaledContents(True)

        scene = QGraphicsScene()
        view = QGraphicsView(scene)
        view.move(400, 15)

        # Create "Previous" and "Next" buttons
        previous_button = QPushButton("Previous", self)
        previous_button.move(1075, 50)
        next_button = QPushButton("Next", self)
        next_button.move(1075, 80)

        # Create "Zoom in" and "Zoom out" buttons
        zoom_in_button = QPushButton("Zoom +", self)
        zoom_in_button.move(1075, 110)
        zoom_in_button.clicked.connect(lambda: self.zoom_in())
        zoom_out_button = QPushButton("Zoom -", self)
        zoom_out_button.move(1075, 140)

        # Load images and initialize image index
        self.image_paths = os.listdir(str(get_path() + '/output/pictures/'))
        self.image_index = 0
        self.load_image()

        scene.addWidget(self.image_label)
        # Connect button clicks to navigation methods
        previous_button.clicked.connect(self.previous_image)
        next_button.clicked.connect(self.next_image)

    def plot_image(self):
        # add matplotlib figure
        fig = Figure(figsize=(5, 5))
        axes = fig.add_subplot(111)
        t = np.linspace(0, 2 * np.pi)
        axes.plot(t, np.sin(t), '-rh', linewidth=3, markersize=5, markerfacecolor='b',
                  label=r'$\ y=sin(x) $')
        axes.grid(color='b', linewidth=1.0)
        axes.legend(fontsize=12)
        # img = r'D:\ГПН\Опорные сетки\well_net\Рисунок3.png'
        # axes.imshow(mpimg.imread(img))
        self.image = FigureCanvas(fig)
        self.toolbar = NavigationToolbar(self.image, self)

        self.window_draw = QVBoxLayout(self)
        self.window_draw.setGeometry(QRect(400, 400, 500, 100))
        self.window_draw.addWidget(self.toolbar)
        self.window_draw.addWidget(self.image.draw())

        # Create a placeholder widget to hold our toolbar and canvas.
        self.widget = QWidget(self)
        self.widget.setLayout(self.window_draw)
        self.widget.setGeometry(400, 400, 500, 100)
        self.widget.show()

    def load_image(self):
        # Load and display the current image
        if 0 <= self.image_index < len(self.image_paths):
            image_path = self.image_paths[self.image_index]
            # return QPixmap('{}\\{}'.format(str(get_path() + '/output/pictures'), image_path))
            # scaled_pixmap = pixmap.scaled()
            self.image_label.setPixmap(QPixmap('{}\\{}'.format(str(get_path() + '/output/pictures'), image_path)))
            self.image_label.setScaledContents(True)

    def previous_image(self):
        # Show the previous image
        if self.image_index > 0:
            self.image_index -= 1
            self.load_image()

    def next_image(self):
        # Show the next image
        if self.image_index < len(self.image_paths) - 1:
            self.image_index += 1
            self.load_image()

    def zoom_in(self):
        size = self.load_image().size()
        scaled_pixmap = self.load_image().scaled(1.25 * size)
        self.image_label.setPixmap(scaled_pixmap)
        # self.image_label.setScaledContents(True)

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
