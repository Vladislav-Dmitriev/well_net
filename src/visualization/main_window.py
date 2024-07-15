import sys

from PyQt6 import QtWidgets, QtCore, QtGui

from qtsample import Ui_MainWindow
from src.main import module_gdis
from src.preparing.validate_widget_data import ValidatorData
from pydantic import TypeAdapter, ValidationError


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        self.ui.treeWidget.expandAll()
        self.ta = TypeAdapter(ValidatorData)
        self.add_combobox()
        self.dict_param = self.get_dict_qtreewidget()
        self.buttons()
        self.item_clicked()
        self.show()

    def validate(self, dict_params):
        list_rename = ['data_file', 'calculation_scenario', 'gdis_option', 'calc_option', 'percent',
                       'horizon_count', 'mult_coef', 'limit_radius_coef', 'min_length_horWell', 'water_cut',
                       'fluid_rate', 'mean_oilrate_option', 'percent_oilrate', 'limit_oilrate', 'limit_research_time',
                       'min_research_time', 'max_research_time', 'option_percent', 'list_order_fond', 'percent_piez',
                       'percent_inj', 'percent_prod', 'separation_by_years', 'max_distance', 'verticalWellAngle',
                       'MaxOverlapPercent', 'angle_horizontalT1', 'angle_horizontalT3']
        dict_params = dict(zip(list_rename, list(dict_params.values())))
        try:
            # print(self.ta.validate_python(dict_params))
            return self.ta.validate_python(dict_params)
        except ValidationError as exc:
            dict_errors = exc.errors()[0]
            wrong_param = dict_errors['loc'][0]
            error_message = dict_errors['msg'].split(',')[-1]
            print(f'Incorrect input parameter: {wrong_param}. {error_message}')
            error_widget = QtWidgets.QMessageBox(self, error_message)
            error_widget.setWindowTitle('Ошибка в значении вводимого параметра')
            error_widget.setText(f'Incorrect input parameter: {wrong_param}. {error_message}')
            error_widget.show()

    def buttons(self):
        # begin calculation button
        self.ui.calculate.clicked.connect(lambda: module_gdis(self.validate(self.dict_param)))
        self.ui.download_previous.clicked.connect(lambda: print(self.validate(self.dict_param)))

    def editable_column(self, item, column):
        """
        Делает редактируемым только 1 столбец со значениями параметров
        :param item: строка виджета
        :param column: столбец виджета
        :return: отредактированный виджет с возможностью редактировать столбец со значениями параметров
        """
        # make only one column of QTreeWidget is editable, items without child
        if column == 1 and item.childCount() == 0:
            item.setFlags(item.flags() | QtCore.Qt.ItemFlag.ItemIsEditable | QtCore.Qt.ItemFlag.ItemIsUserCheckable)
            self.ui.treeWidget.editItem(item, column)

    def item_clicked(self):
        """
        При нажатии на ячейку в столбце доступном для редактирования открываетсся возможность редактировать ее значение
        :return: редактирование ячейки пользователем
        """
        # check clicked item of QTreeWidget
        self.ui.treeWidget.itemClicked.connect(self.editable_column)
        # check change in item and update global dictionary of parameters
        self.ui.treeWidget.itemChanged.connect(self.update_dict)

    def combobox_scenario(self, value):
        """
        Изменяет значение в словаре параметров по ключу при изменении значения combobox
        :param value: значение виджета combobox после изменения
        :return: обновленное значение словаря параметров по ключу item, где находится текущий combobox
        """
        # print('Сценарий расчета', value)
        self.dict_param['Сценарий расчета'] = value
        self.update_dict()

    def combobox_gdis(self, value):
        """
        Изменяет значение в словаре параметров по ключу при изменении занчения combobox
        :param value: значение виджета combobox после изменения
        :return: обновленное значение словаря параметров по ключу item, где находится текущий combobox
        """
        # print('Распред-ие ГДИС скв. по годам', value)
        self.dict_param['Распред-ие ГДИС скв. по годам'] = value
        self.update_dict()

    def combobox_y_n(self, value):
        """
        Изменяет значение в словаре параметров по ключу при изменении занчения combobox
        :param value: значение виджета combobox после изменения
        :return: обновленное значение словаря параметров по ключу item, где находится текущий combobox
        """
        # print('Критерий охвата траектории ГС', value)
        self.dict_param['Критерий охвата траектории ГС'] = value
        self.update_dict()

    def combobox_y_n2(self, value):
        """
        Изменяет значение в словаре параметров по ключу при изменении занчения combobox
        :param value: значение виджета combobox после изменения
        :return: обновленное значение словаря параметров по ключу item, где находится текущий combobox
        """
        # print('Учет Q ср. по объекту', value)
        self.dict_param['Учет Q ср. по объекту'] = value
        self.update_dict()

    def combobox_y_n3(self, value):
        """
        Изменяет значение в словаре параметров по ключу при изменении занчения combobox
        :param value: значение виджета combobox после изменения
        :return: обновленное значение словаря параметров по ключу item, где находится текущий combobox
        """
        # print('Учет границ исслед. ННС/ГС', value)
        self.dict_param['Учет границ исслед. ННС/ГС'] = value
        self.update_dict()

    def combobox_y_n4(self, value):
        """
        Изменяет значение в словаре параметров по ключу при изменении занчения combobox
        :param value: значение виджета combobox после изменения
        :return: обновленное значение словаря параметров по ключу item, где находится текущий combobox
        """
        # print('Учет % от каждого фонда', value)
        self.dict_param['Учет % от каждого фонда'] = value
        self.update_dict()

    def update_dict(self):
        """
        Обвовление всех значений словаря параметров, тк один из item-ов был изменен
        :return: обновленный словарь значений параметров
        """
        self.dict_param.update(self.get_dict_qtreewidget())
        self.validate(self.dict_param)

    def get_dict_qtreewidget(self):
        """

        :return:
        """
        dict_qtreewiget = {}
        list_combobox_items = ['Критерий охвата траектории ГС', 'Учет Q ср. по объекту', 'Учет границ исслед. ННС/ГС',
                               'Учет % от каждого фонда', 'Сценарий расчета', 'Распред-ие ГДИС скв. по годам']
        self.ui.treeWidget.update()
        iterator = QtWidgets.QTreeWidgetItemIterator(self.ui.treeWidget)
        while iterator.value():
            item = iterator.value()
            if item.childCount() == 0:
                if item.text(0) in list_combobox_items:
                    dict_qtreewiget[f'{item.text(0)}'] = self.ui.treeWidget.itemWidget(item, 1).currentText()
                else:
                    dict_qtreewiget[f'{item.text(0)}'] = item.text(1)
            iterator += 1

        # dict_qtreewiget = dict(zip(list_rename, list(dict_qtreewiget.values())))

        return dict_qtreewiget

    def add_combobox(self):
        """
        Добавление виджета ComboBox в Item, где есть только ограниченный выбор параметров расчета
        :return:
        """
        list_combobox_items = ['Критерий охвата траектории ГС', 'Учет Q ср. по объекту', 'Учет границ исслед. ННС/ГС',
                               'Учет % от каждого фонда', 'Сценарий расчета', 'Распред-ие ГДИС скв. по годам']
        for name in list_combobox_items:
            current_item = self.ui.treeWidget.findItems(name, QtCore.Qt.MatchFlag.MatchContains | QtCore.Qt.MatchFlag.MatchRecursive, 0)[0]
            combobox = QtWidgets.QComboBox()
            if name == 'Сценарий расчета':
                combobox.addItem('Оптимальная сетка')
                combobox.addItem('Регулярная сетка')
                self.ui.treeWidget.setItemWidget(current_item, 1, combobox)
                combobox.currentTextChanged.connect(self.combobox_scenario)
                continue
            elif name == 'Распред-ие ГДИС скв. по годам':
                combobox.addItem('0')
                combobox.addItem('1')
                combobox.addItem('2')
                self.ui.treeWidget.setItemWidget(current_item, 1, combobox)
                combobox.currentTextChanged.connect(self.combobox_gdis)
                continue

            elif name == 'Критерий охвата траектории ГС':
                combobox.addItem('Да')
                combobox.addItem('Нет')
                self.ui.treeWidget.setItemWidget(current_item, 1, combobox)
                combobox.currentTextChanged.connect(self.combobox_y_n)
                continue

            elif name == 'Учет Q ср. по объекту':
                combobox.addItem('Да')
                combobox.addItem('Нет')
                self.ui.treeWidget.setItemWidget(current_item, 1, combobox)
                combobox.currentTextChanged.connect(self.combobox_y_n2)
                continue
            elif name == 'Учет границ исслед. ННС/ГС':
                combobox.addItem('Да')
                combobox.addItem('Нет')
                self.ui.treeWidget.setItemWidget(current_item, 1, combobox)
                combobox.currentTextChanged.connect(self.combobox_y_n3)
                continue
            else:
                combobox.addItem('Да')
                combobox.addItem('Нет')
                self.ui.treeWidget.setItemWidget(current_item, 1, combobox)
                combobox.currentTextChanged.connect(self.combobox_y_n4)
                continue


class ErrorWindow(QtWidgets.QMessageBox):
    def __init__(self, message, parent=QtWidgets.QWidget):
        super().__init__()
        self.setWindowTitle('Ошибка в параметрах')
        self.setText(message)
        self.resize(400, 200)
        self.show()


if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    window = MainWindow()
    sys.exit(app.exec())
