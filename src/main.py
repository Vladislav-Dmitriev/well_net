import sys
import os
from src.gui.main_window import MainWindow
from PyQt6 import QtWidgets, QtGui
from src.calculation.support_functions import get_path


def start_application():
    """Запускает PyQt приложение"""
    app = QtWidgets.QApplication(sys.argv)
    window = MainWindow()
    window.setWindowTitle('Модуль ОС')
    window.setWindowIcon(QtGui.QIcon(os.path.join(get_path(), "Icon.ico")))
    sys.exit(app.exec())


if __name__ == "__main__":
    start_application()
