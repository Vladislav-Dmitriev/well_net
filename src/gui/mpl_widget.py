from PyQt6.QtWidgets import *
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import (NavigationToolbar2QT as NavigationToolbar)
import matplotlib.pyplot as plt
from src.gui.plot_design import plot_results


class MplWidget(QWidget):
    def __init__(self, df_results, script, parent=None):
        super().__init__(parent)

        self.my_layout = QVBoxLayout(self)

        # Вызов функции построения графика и получение figure и axes
        fig, ax = plot_results(df_results, script)

        # Создание canvas для вывода графика
        self.canvas = FigureCanvas(fig)
        self.canvas.axes = ax

        # Добавление панели инструментов для взаимодействия с графиком
        self.toolbar = NavigationToolbar(self.canvas, self)

        # Установка вертикального layout и добавление элементов в виджет
        self.my_layout.addWidget(self.toolbar)
        self.my_layout.addWidget(self.canvas)

        self.setLayout(self.my_layout)