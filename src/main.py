import sys
from src.gui.main_window import MainWindow
from PyQt6 import QtWidgets, QtGui


def start_application():
    """Запускает PyQt приложение"""
    app = QtWidgets.QApplication(sys.argv)
    window = MainWindow()
    window.setWindowTitle('Модуль ОС')
    window.setWindowIcon(QtGui.QIcon('Icon.png'))
    sys.exit(app.exec())


if __name__ == "__main__":
    start_application()
