from PyQt6.QtWidgets import *
from PyQt6.uic import loadUi
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import (NavigationToolbar2QT as NavigationToolbar)
from matplotlib.figure import Figure
import random


class MplWidget(QWidget):

    def __init__(self, parent):
        QMainWindow.__init__(self, parent)

        super().__init__(parent)
        self.canvas = FigureCanvas(Figure())
        self.canvas.axes = self.canvas.figure.add_subplot(111)
        self.canvas.axes.plot([random.random() for i in range(200)])
        self.toolbar = NavigationToolbar(self.canvas)

        vertical_layout = QVBoxLayout()
        vertical_layout.addWidget(self.toolbar)
        vertical_layout.addWidget(self.canvas)

        self.setLayout(vertical_layout)
