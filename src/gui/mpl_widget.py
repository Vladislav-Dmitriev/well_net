from PyQt6 import QtWidgets
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import (NavigationToolbar2QT as NavigationToolbar)
from src.gui.plot_design import plot_results


class MplWidget(QtWidgets.QWidget):
    def __init__(self, df_results, script, parent=None):
        super().__init__(parent)

        self.my_layout = QtWidgets.QVBoxLayout(self)

        # Вызов функции построения графика и получение figure и axes
        self.fig, self.ax, self.check = plot_results(df_results, script)
        # Создание canvas для вывода графика
        self.canvas = FigureCanvas(self.fig)
        # Добавление панели инструментов для взаимодействия с графиком
        self.toolbar = NavigationToolbar(self.canvas, self)

        # Установка вертикального layout и добавление элементов в виджет
        self.my_layout.addWidget(self.toolbar)
        self.my_layout.addWidget(self.canvas)

        self.setLayout(self.my_layout)
