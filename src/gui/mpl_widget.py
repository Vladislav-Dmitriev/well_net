from PyQt6 import QtWidgets
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import (NavigationToolbar2QT as NavigationToolbar)
from src.gui.plot_design import plot_results


# Кастомный toolbar без кнопок изменения осей
class CustomNavigationToolbar(NavigationToolbar):
    toolitems = [t for t in NavigationToolbar.toolitems if t[0] not in ('Subplots', 'Customize')]

    def __init__(self, canvas, parent=None):
        super().__init__(canvas, parent)

    def save_figure(self):
        # Открываем диалог для выбора имени файла
        filename, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Сохранить изображение", "", "JPEG Files (*.jpg);;All Files (*)"
        )
        if filename:
            # Заданные параметры
            width_pixels = 25000  # Ширина в пикселях
            height_pixels = 25000  # Высота в пикселях
            dpi = 300  # Разрешение в DPI

            # Рассчитываем размер фигуры в дюймах
            figsize = (width_pixels / dpi, height_pixels / dpi)

            # Устанавливаем временный размер фигуры
            original_figsize = self.canvas.figure.get_size_inches()  # Сохраняем текущий размер
            self.canvas.figure.set_size_inches(figsize)  # Задаем новый размер

            # Сохраняем график
            self.canvas.figure.savefig(filename, dpi=dpi, format="jpeg")

            # Восстанавливаем оригинальный размер
            self.canvas.figure.set_size_inches(original_figsize)  # Возвращаем исходный размер


class MplWidget(QtWidgets.QWidget):
    def __init__(self, df_results, script, parent=None):
        super().__init__(parent)

        self.my_layout = QtWidgets.QVBoxLayout(self)

        # Вызов функции построения графика и получение figure и axes
        self.fig, self.ax, self.check = plot_results(df_results, script)

        self.fig.set_constrained_layout(True)
        self.ax.set_aspect('equal')
        self.ax.set_adjustable('datalim')

        self.canvas = FigureCanvas(self.fig)
        self.toolbar = CustomNavigationToolbar(self.canvas, self)

        self.my_layout.addWidget(self.toolbar)
        self.my_layout.addWidget(self.canvas)

        self.setLayout(self.my_layout)

    def resizeEvent(self, event):
        # Получаем новый размер окна
        width = self.width()
        height = self.height()

        # Устанавливаем новый размер графика
        self.fig.set_size_inches(width / 100, height / 100, forward=True)

        # Перерисовываем canvas
        self.canvas.draw_idle()
