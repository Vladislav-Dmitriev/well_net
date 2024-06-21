import sys

from PyQt6 import QtWidgets

from qtsample import Ui_MainWindow
from src.main import module_gdis


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        self.buttons()
        self.show()

    def buttons(self):
        self.ui.pushButton_2.clicked.connect(lambda: module_gdis())

    def editable_column(self, item, column):
        return item


if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    window = MainWindow()
    sys.exit(app.exec())
