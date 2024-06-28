import sys

from PyQt6 import QtWidgets, QtCore, QtGui
from pydantic import BaseModel

from qtsample import Ui_MainWindow
from src.main import module_gdis


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        self.buttons()
        self.item_clicked()
        self.get_val_qtreewidget()
        self.show()

    def buttons(self):
        # begin calculation button
        self.ui.pushButton_2.clicked.connect(lambda: module_gdis())

    def editable_column(self, item, column):
        # make only one column of QTreeWidget is editable, items without child
        if column == 1 and item.childCount() == 0:
            item.setFlags(item.flags() | QtCore.Qt.ItemFlag.ItemIsEditable)
            self.ui.treeWidget.editItem(item, column)

    def item_clicked(self):
        # check clicked item of QTreeWidget
        self.ui.treeWidget.itemClicked.connect(self.editable_column)

    def get_val_qtreewidget(self):
        dict_qtreewiget = {}
        iterator = QtWidgets.QTreeWidgetItemIterator(self.ui.treeWidget)
        while iterator.value():
            item = iterator.value()
            if item.childCount() == 0:
                dict_qtreewiget[f'{item.text(0)}'] = item.text(1)
            iterator += 1
        print(dict_qtreewiget)
        return dict_qtreewiget


# class ValidatorData(BaseModel):


if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    window = MainWindow()
    sys.exit(app.exec())
