import sys
import os
import pandas as pd
import sqlite3 as sql
import xlwings as xw

from PyQt6 import QtWidgets, QtCore, QtGui

from qtsample import Ui_MainWindow
from src.main import module_gdis
from src.preparing.validate_widget_data import ValidatorData
from pydantic import TypeAdapter, ValidationError
from src.calculation.auxiliary_functions import get_path


class DataframeToTable(QtCore.QAbstractTableModel):

    def __init__(self, data: pd.DataFrame):
        super().__init__()
        self._data = data

    def rowCount(self, parent=None):
        return self._data.shape[0]

    def columnCount(self, parent=None):
        return self._data.shape[1]

    def data(self, index, role=QtCore.Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        if role == QtCore.Qt.ItemDataRole.DisplayRole:
            return str(self._data.iloc[index.row(), index.column()])
        return None

    def headerData(self, section, orientation, role=QtCore.Qt.ItemDataRole.DisplayRole):
        if role == QtCore.Qt.ItemDataRole.DisplayRole:
            if orientation == QtCore.Qt.Orientation.Horizontal:
                return self._data.columns[section]
            elif orientation == QtCore.Qt.Orientation.Vertical:
                return str(self._data.index[section])
        return None


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        self.ui.treeWidget.expandAll()
        self.ta = TypeAdapter(ValidatorData)
        self.add_combobox()
        self.dict_param = self.get_dict_qtreewidget()
        self.set_default_params()
        self.combobox_scen_switch()
        self.buttons()
        self.item_clicked()
        self.menu_()
        self.show()

    def set_default_params(self):
        """
        Загрузка параметров из базы данных по умолчанию
        :return: виджет со значениями параметров расчета
        """
        path = f'{get_path()}\\input\\wellnet_input.db'
        connection = sql.connect(path)
        dict_default = pd.read_sql_query("SELECT * FROM parameters", connection).to_dict(orient='records')[0]
        list_boolean_params = ['Критерий охвата траектории ГС', 'Учет Q ср. по объекту',
                               'Учет границ исслед. ННС/ГС', 'Учет % от каждого фонда']
        list_combobox_items = ['Сценарий расчета', 'Распред-ие ГДИС скв. по годам']

        iterator = QtWidgets.QTreeWidgetItemIterator(self.ui.treeWidget)
        while iterator.value():
            item = iterator.value()
            if item.childCount() == 0:
                if (item.text(0) not in list_combobox_items) and (item.text(0) not in list_boolean_params):
                    item.setText(1, str(dict_default[f'{item.text(0)}']))
                elif item.text(0) in list_combobox_items:
                    self.ui.treeWidget.itemWidget(item, 1).setCurrentText(dict_default[item.text(0)])
                else:
                    self.ui.treeWidget.itemWidget(item, 1).setCurrentText(dict_default[item.text(0)])

            iterator += 1

        connection.close()

    def default_table_names(self):
        """
        Считывание из БД по умолчанию таблиц результатов расчета для добавления в ComboBox
        :return: список с именами таблиц результатов из БД по умолчанию
        """
        path = f'{get_path()}\\input\\wellnet_input.db'
        connection = sql.connect(path)
        cursor = connection.cursor()
        list_of_names = [x[0] for x in
                         cursor.execute('''SELECT name FROM sqlite_master WHERE type='table';''').fetchall() if
                         x[0] != 'parameters' and x[0] != 'report']

        return list_of_names

    def get_result_table(self, value):
        """
        Загрузка и вывод таблиц в виджет
        :param value:
        :return:
        """
        path = f'{get_path()}\\input\\wellnet_input.db'
        connection = sql.connect(path)
        df = pd.read_sql_query(f'SELECT * FROM "{value}"', connection)
        df = df.drop(columns=['index'])
        df = df.fillna(0)
        connection.close()
        model = DataframeToTable(df)
        self.ui.results.setModel(model)

    def menu_(self):
        """
        Меню
        :return:
        """
        self.ui.readme_txt.triggered.connect(lambda: os.startfile(f'{get_path()}//README.txt'))
        self.ui.reference.triggered.connect(lambda: os.startfile(f'{get_path()}//Методичка ОС.docx'))
        self.ui.exit.triggered.connect(QtCore.QCoreApplication.instance().quit)
        self.ui.open_project.triggered.connect(lambda:
                                               QtWidgets.QFileDialog.getExistingDirectory(self,
                                                                                          "Выберите файл с"
                                                                                          " результатами предыдущих"
                                                                                          " расчетов",
                                                                                          f'{get_path()}\\output'))

    def validate(self, dict_params, dict_previous):
        """
        Функция валидации параметров расчета
        :param dict_params:
        :param dict_previous:
        :return:
        """
        list_rename = ['data_file', 'calculation_scenario', 'gdis_option', 'calc_option', 'percent',
                       'horizon_count', 'mult_coef', 'limit_radius_coef', 'min_length_horWell', 'water_cut',
                       'fluid_rate', 'mean_oilrate_option', 'percent_oilrate', 'limit_oilrate', 'limit_research_time',
                       'min_research_time', 'max_research_time', 'option_percent', 'list_order_fond', 'percent_piez',
                       'percent_inj', 'percent_prod', 'separation_by_years', 'max_distance', 'verticalWellAngle',
                       'MaxOverlapPercent', 'angle_horizontalT1', 'angle_horizontalT3']
        list_visible_names = list(dict_params.keys())
        dict_params = dict(zip(list_rename, list(dict_params.values())))
        try:
            return self.ta.validate_python(dict_params)
        except ValidationError as exc:
            dict_errors = exc.errors()[0]
            wrong_param_index = list_rename.index(dict_errors['loc'][0])
            wrong_param = list_visible_names[wrong_param_index]
            error_message = dict_errors['msg'].split(',')[-1]
            # print(f'Incorrect input parameter: {wrong_param}. {error_message}')
            self.message_box(f'Incorrect input parameter: {wrong_param}. {error_message.strip().capitalize()}')
            current_item = self.ui.treeWidget.findItems(wrong_param, QtCore.Qt.MatchFlag.MatchContains |
                                                        QtCore.Qt.MatchFlag.MatchRecursive, 0)[0]
            # возвращение предыдущего значения ячейки при неверно введенном формате параметра
            current_item.setText(1, dict_previous[wrong_param])

    def message_box(self, message):
        QtWidgets.QMessageBox.about(self, 'Ошибка в значении введенного параметра', message)

    def buttons(self):
        # begin calculation button
        self.ui.calculate.clicked.connect(lambda: module_gdis(self.validate(self.dict_param, self.dict_param),
                                                              self.ui.path_result_db.text()))
        # save current table in Excel
        self.ui.save_table.clicked.connect(lambda: self.table_to_excel(
            QtWidgets.QFileDialog.getSaveFileName(self, "Сохранение таблицы опорной сетки",
                                                  f'{get_path()}\\output\\well_net.xlsx',
                                                  filter='Excel (*.xlsx *.xls)'),
            [self.ui.combobox_scenario.currentText()]))
        # save all tables in Excel
        self.ui.save_all_tables.clicked.connect(lambda: self.table_to_excel(
            QtWidgets.QFileDialog.getSaveFileName(self, "Сохранение таблицы опорной сетки",
                                                  f'{get_path()}\\output\\well_net.xlsx',
                                                  filter='Excel (*.xlsx *.xls)'),
            [self.ui.combobox_scenario.itemText(i) for i in range(self.ui.combobox_scenario.count())] + ["report"]))
        # choosing directory to save database
        self.ui.choose_directory.clicked.connect(lambda:
                                                 self.ui.path_result_db.
                                                 setText(QtWidgets.QFileDialog.getSaveFileName(self, "Директория сохранения результатов расчета", f'{get_path()}\\output\\wellnet_result.db')[0]))

    def table_to_excel(self, path_to_save, list_names):
        """
        Сохранение таблицы/таблиц в Excel файл
        :param path_to_save: путь к БД, сформированной после расчета
        :param list_names:
        :return:
        """
        if self.ui.path_result_db.text() != '':
            path = self.ui.path_result_db.text()
        else:
            path = f'{get_path()}\\input\\wellnet_input.db'
        connection = sql.connect(path)
        app1 = xw.App(visible=False)
        new_wb = xw.Book()
        for name in list_names:
            df = pd.read_sql_query(f'SELECT * FROM "{name}"', connection)
            df = df.drop(columns=['index'])
            df = df.fillna(0)
            new_wb.sheets.add(f"{name}")
            sht = new_wb.sheets(f"{name}")
            sht.range('A1').options().value = df
        new_wb.save(path_to_save[0])
        app1.kill()
        connection.close()

    def write_dict(self):
        """
        Функция считывает параметры расчета из виджета и записывает их в БД
        :return:
        """
        # подключение к БД
        path = f'{get_path()}\\output\\wellnet_result.db'
        connection = sql.connect(path)
        # запись параметров расчета по умолчанию из подготовленной БД
        cursor = connection.cursor()
        cursor.execute('''DROP TABLE IF EXISTS parameters''')
        # подготовка словаря с параметрами расчета для записи в БД
        columns = self.dict_param.keys()
        placeholders = ', '.join(['?'] * len(self.dict_param))
        values = tuple(self.dict_param.values())

        cursor.execute(f'CREATE TABLE IF NOT EXISTS parameters {tuple(columns)}')
        cursor.execute(f'INSERT INTO parameters {tuple(columns)} VALUES ({placeholders})', values)

        connection.commit()
        connection.close()

    def editable_column(self, item, column):
        """
        Делает редактируемым только 1 столбец со значениями параметров
        :param item: строка виджета
        :param column: столбец виджета
        :return: отредактированный виджет с возможностью редактировать столбец со значениями параметров
        """
        # make only one column of QTreeWidget is editable, items without child
        if column == 1 and item.childCount() == 0:
            item.setFlags(item.flags() | QtCore.Qt.ItemFlag.ItemIsEditable | QtCore.Qt.ItemFlag.ItemIsUserCheckable |
                          QtCore.Qt.ItemFlag.ItemIsSelectable)
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

    def combobox_scen_switch(self):

        list_scen = self.default_table_names()
        for scen in list_scen:
            self.ui.combobox_scenario.addItem(scen)
        path = f'{get_path()}\\input\\wellnet_input.db'
        connection = sql.connect(path)
        df = pd.read_sql_query(f'SELECT * FROM "{list_scen[0]}"', connection)
        df_report = pd.read_sql_query(f'SELECT * FROM "report"', connection)
        df = df.drop(columns=['index'])
        df = df.fillna(0)
        df_report = df_report.drop(columns=['index'])
        df_report = df_report.fillna(0)
        connection.close()
        model = DataframeToTable(df)
        model_report = DataframeToTable(df_report)
        self.ui.results.setModel(model)
        self.ui.report.setModel(model_report)
        self.ui.combobox_scenario.currentTextChanged.connect(self.get_result_table)

    def combobox_scenario(self, value):
        """
        Изменяет значение в словаре параметров по ключу при изменении значения combobox
        :param value: значение виджета combobox после изменения
        :return: обновленное значение словаря параметров по ключу item, где находится текущий combobox
        """
        self.dict_param['Сценарий расчета'] = value
        self.update_dict()

    def combobox_gdis(self, value):
        """
        Изменяет значение в словаре параметров по ключу при изменении занчения combobox
        :param value: значение виджета combobox после изменения
        :return: обновленное значение словаря параметров по ключу item, где находится текущий combobox
        """
        self.dict_param['Распред-ие ГДИС скв. по годам'] = value
        self.update_dict()

    def combobox_coverage_traj_hw(self, value):
        """
        Изменяет значение в словаре параметров по ключу при изменении значения combobox
        :param value: значение виджета combobox после изменения
        :return: обновленное значение словаря параметров по ключу item, где находится текущий combobox
        """
        self.dict_param['Критерий охвата траектории ГС'] = value
        self.update_dict()

    def combobox_average_flowrate(self, value):
        """
        Изменяет значение в словаре параметров по ключу при изменении значения combobox
        :param value: значение виджета combobox после изменения
        :return: обновленное значение словаря параметров по ключу item, где находится текущий combobox
        """
        self.dict_param['Учет Q ср. по объекту'] = value
        self.update_dict()

    def combobox_time_boundaries(self, value):
        """
        Изменяет значение в словаре параметров по ключу при изменении занчения combobox
        :param value: значение виджета combobox после изменения
        :return: обновленное значение словаря параметров по ключу item, где находится текущий combobox
        """
        self.dict_param['Учет границ исслед. ННС/ГС'] = value
        self.update_dict()

    def combobox_criteria_y_n(self, value):
        """
        Изменяет значение в словаре параметров по ключу при изменении значения combobox
        :param value: значение виджета combobox после изменения
        :return: обновленное значение словаря параметров по ключу item, где находится текущий combobox
        """
        self.dict_param['Учет % от каждого фонда'] = value
        self.update_dict()

    def update_dict(self):
        """
        Обвовление всех значений словаря параметров, тк один из item-ов был изменен
        :return: обновленный словарь значений параметров
        """
        # копирования словаря на случай, если будет введено неверное значение
        # какого-либо параметра - возвращается предыдущее значение
        dict_previous = self.dict_param.copy()
        self.dict_param.update(self.get_dict_qtreewidget())
        self.validate(self.dict_param, dict_previous)

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

        return dict_qtreewiget

    def add_combobox(self):
        """
        Добавление виджета ComboBox в Item, где есть только ограниченный выбор параметров расчета
        :return:
        """
        list_combobox_items = ['Критерий охвата траектории ГС', 'Учет Q ср. по объекту', 'Учет границ исслед. ННС/ГС',
                               'Учет % от каждого фонда', 'Сценарий расчета', 'Распред-ие ГДИС скв. по годам']
        for name in list_combobox_items:
            current_item = self.ui.treeWidget.findItems(name, QtCore.Qt.MatchFlag.MatchContains |
                                                        QtCore.Qt.MatchFlag.MatchRecursive, 0)[0]
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
                combobox.currentTextChanged.connect(self.combobox_coverage_traj_hw)
                continue

            elif name == 'Учет Q ср. по объекту':
                combobox.addItem('Да')
                combobox.addItem('Нет')
                self.ui.treeWidget.setItemWidget(current_item, 1, combobox)
                combobox.currentTextChanged.connect(self.combobox_average_flowrate)
                continue
            elif name == 'Учет границ исслед. ННС/ГС':
                combobox.addItem('Да')
                combobox.addItem('Нет')
                self.ui.treeWidget.setItemWidget(current_item, 1, combobox)
                combobox.currentTextChanged.connect(self.combobox_time_boundaries)
                continue
            else:
                combobox.addItem('Да')
                combobox.addItem('Нет')
                self.ui.treeWidget.setItemWidget(current_item, 1, combobox)
                combobox.currentTextChanged.connect(self.combobox_criteria_y_n)
                continue


if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    window = MainWindow()
    sys.exit(app.exec())
