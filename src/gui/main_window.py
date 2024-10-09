import sys
import os
import pandas as pd
import sqlite3 as sql
import xlwings as xw
from datetime import datetime
from loguru import logger
from PyQt6 import QtWidgets, QtCore, QtGui
from qtsample import Ui_MainWindow
from src.main import module_gdis
from src.gui.validate_widget_data import ValidateData, ValidatePath
from pydantic import ValidationError
from src.calculation.support_functions import get_path


class LogWindow(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowTitle('Выполнение расчета')
        self.setGeometry(100, 100, 600, 400)

        self.log_text = QtWidgets.QTextEdit(self)
        self.log_text.setReadOnly(True)

        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(self.log_text)
        self.setLayout(layout)

    def append_log(self, message):
        """
        Add text to the log
        :param message:
        :return:
        """
        self.log_text.append(message)
        self.log_text.ensureCursorVisible()


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


class FileDirectWidget(QtWidgets.QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.line_edit = QtWidgets.QLineEdit(self)
        self.button_path = QtWidgets.QPushButton("...", self)
        self.button_path.setMaximumWidth(30)

        layout = QtWidgets.QHBoxLayout(self)
        layout.addWidget(self.line_edit)
        layout.addWidget(self.button_path)
        layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(layout)

        self.line_edit.setText(os.path.join(get_path(), 'input', 'Фонд_Новопортовское.xlsx'))


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        self.ui.treeWidget.expandAll()
        self.filedir_widget()
        self.add_combobox()
        self.set_default_params()
        self.dict_param = self.get_dict_qtreewidget()
        self.filedir_actions()
        self.combobox_actions()
        self.database_path = f'{get_path()}\\output\\wellnet_default.db'
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
        path = f'{get_path()}\\output\\wellnet_default.db'
        connection = sql.connect(path)
        dict_default = pd.read_sql_query("SELECT * FROM parameters", connection).to_dict(orient='records')[0]
        list_boolean_params = ['Критерий охвата траектории ГС', 'Учет Q ср. по объекту',
                               'Учет границ исслед. ННС/ГС', 'Учет % от каждого фонда']
        list_combobox_items = ['Сценарий расчета', 'Распред-ие ГДИС скв. по годам']
        list_custom_items = ['Файл с данными']

        iterator = QtWidgets.QTreeWidgetItemIterator(self.ui.treeWidget)
        while iterator.value():
            item = iterator.value()
            if item.childCount() == 0:
                if item.text(0) in list_custom_items:
                    self.ui.treeWidget.itemWidget(item, 1).line_edit.setText(dict_default[item.text(0)])
                elif item.text(0) in list_combobox_items:
                    self.ui.treeWidget.itemWidget(item, 1).setCurrentText(dict_default[item.text(0)])
                elif item.text(0) in list_boolean_params:
                    self.ui.treeWidget.itemWidget(item, 1).setCurrentText(dict_default[item.text(0)])
                else:
                    item.setText(1, str(dict_default[f'{item.text(0)}']))

            iterator += 1

        connection.close()

        self.ui.path_result_db.setText(f'{get_path()}\\output\\{os.getlogin()}_'
                                                     f'{datetime.now().strftime("%Y-%m-%d %H-%M-%S")}.db')

    def menu_(self):
        """
        :return: действия на кнопки меню
        """
        self.ui.readme_txt.triggered.connect(lambda: os.startfile(f'{get_path()}//README.txt'))
        self.ui.reference.triggered.connect(lambda: os.startfile(f'{get_path()}//Методичка ОС.docx'))
        self.ui.exit.triggered.connect(QtCore.QCoreApplication.instance().quit)
        self.ui.open_project.triggered.connect(lambda:
                                               QtWidgets.QFileDialog.getOpenFileName(self,
                                                                                     "Выберите файл с"
                                                                                     " результатами предыдущих"
                                                                                     " расчетов",
                                                                                     f'{get_path()}\\output',
                                                                                     filter='Database (*.db)'))

    def validate_path_db(self):
        """
        Если пользователь вводит несуществующую директорию, путь формируется автоматически.
        :return: Заполняет поле пути сохранения базы данных после расчета
        """
        try:
            path_save_db = ValidatePath(path=self.ui.path_result_db.text()).path
            self.ui.path_result_db.setText(path_save_db)
        except ValidationError as e:
            self.message_box(f'Incorrect input parameter: "Сохранение результатов".'
                             f' The parameter value will be set to default.')
            self.ui.path_result_db.setText(f'{get_path()}\\output\\{os.getlogin()}_'
                                                     f'{datetime.now().strftime("%Y-%m-%d %H-%M-%S")}.db')

    def validate(self, dict_params, dict_previous):
        """
        Функция валидации параметров расчета
        :param dict_params:
        :param dict_previous: словарь со значениями параметров до изменения
        :return: если введенный пользователем параметр имеет некорректное значение,
         то возвращаются параметры из старого словаря
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
            return ValidateData(**dict_params).dict()
        except ValidationError as exc:
            dict_errors = exc.errors()[0]
            wrong_param_index = list_rename.index(dict_errors['loc'][0])
            wrong_param = list_visible_names[wrong_param_index]
            error_message = dict_errors['msg'].split(',')[-1]
            self.message_box(f'Incorrect input parameter: {wrong_param}. {error_message.strip().capitalize()}')
            current_item = self.ui.treeWidget.findItems(wrong_param, QtCore.Qt.MatchFlag.MatchContains |
                                                        QtCore.Qt.MatchFlag.MatchRecursive, 0)[0]
            # возвращение предыдущего значения ячейки при неверно введенном формате параметра
            if isinstance(self.ui.treeWidget.itemWidget(current_item, 1), FileDirectWidget):
                self.ui.treeWidget.itemWidget(current_item, 1).layout().itemAt(0).widget().setText(
                    dict_previous[wrong_param])
            else:
                current_item.setText(1, dict_previous[wrong_param])

    def filedir_widget(self):
        """
        Добавление виджета с помощью класса в item с путем к файлу данных для расчета
        :return:
        """
        filedir_item = self.ui.treeWidget.findItems('Файл с данными', QtCore.Qt.MatchFlag.MatchContains |
                                               QtCore.Qt.MatchFlag.MatchRecursive, 0)[0]
        self.ui.treeWidget.setItemWidget(filedir_item, 1, FileDirectWidget(self))

    def filedir_actions(self):
        """
        Вызов функции валидации словаря параметров при изменении пути к файлу с данными вручную и
        открытие диалогового окна для выбора файла с данными, показаны файлы только формата .xlsx
        :return:
        """
        filedir_item = self.ui.treeWidget.findItems('Файл с данными', QtCore.Qt.MatchFlag.MatchContains |
                                                    QtCore.Qt.MatchFlag.MatchRecursive, 0)[0]
        (self.ui.treeWidget.itemWidget(filedir_item, 1).layout().itemAt(0).widget().
         editingFinished.connect(lambda: self.update_dict()))
        (self.ui.treeWidget.itemWidget(filedir_item, 1).layout().itemAt(1).widget().
         pressed.connect(lambda: self.open_filedialog(filedir_item)))

    def open_filedialog(self, filedir_item):
        """
        Функция открытия диалогового окна для помещения пути файла с данными в виджет параметров расчета
        :param filedir_item: item, в котором находится виджет с путем к файлу с данными
        :return:
        """
        self.ui.treeWidget.itemWidget(filedir_item, 1).layout().itemAt(0).widget().setText(
            QtWidgets.QFileDialog.getOpenFileName(self, 'Выберите файл с данными',
                                                  f'{get_path()}\\input', filter='Excel Files(*.xlsx)')[0])
        self.update_dict()

    def message_box(self, message):
        """
        :param message: текст сообщения для пользователя
        :return: выводится окно об ошибочном вводе параметра расчета
        """
        QtWidgets.QMessageBox.about(self, 'Ошибка в значении введенного параметра', message)

    def buttons(self):
        """
        :return: действия на все кнопки в окне приложения
        """
        # begin calculation button
        self.ui.calculate.clicked.connect(self.main_calc_function)

        # save current table in Excel
        self.ui.save_table.clicked.connect(lambda: self.table_to_excel(
            QtWidgets.QFileDialog.getSaveFileName(self, "Сохранение таблицы опорной сетки",
                                                  f'{get_path()}\\output\\{self.dict_param['Сценарий расчета']}'
                                                  f'_{os.getlogin()}_'
                                                  f'{datetime.now().strftime("%Y-%m-%d %H-%M-%S")}.xlsx',
                                                  filter='Excel (*.xlsx *.xls)'),
            [self.ui.combobox_scenario.currentText()]))
        # save all tables in Excel
        self.ui.save_all_tables.clicked.connect(lambda: self.table_to_excel(
            QtWidgets.QFileDialog.getSaveFileName(self, "Сохранение таблицы опорной сетки",
                                                  f'{get_path()}\\output\\{self.dict_param['Сценарий расчета']}'
                                                  f'_{os.getlogin()}_'
                                                  f'{datetime.now().strftime("%Y-%m-%d %H-%M-%S")}.xlsx',
                                                  filter='Excel (*.xlsx *.xls)'),
            [self.ui.combobox_scenario.itemText(i) for i in range(self.ui.combobox_scenario.count())] + ["report"]))
        # choosing directory to save database
        self.ui.choose_directory.clicked.connect(lambda:
                                                 self.ui.path_result_db.
                                                 setText(QtWidgets.QFileDialog.getSaveFileName(
                                                     self, "Директория сохранения результатов расчета",
                                                     f'{get_path()}\\output\\{os.getlogin()}_'
                                                     f'{datetime.now().strftime("%Y-%m-%d %H-%M-%S")}.db',
                                                     filter='Database (*.db)')[0]))
        # check editing finished QLineEdit with database path
        self.ui.path_result_db.editingFinished.connect(self.validate_path_db)

    def main_calc_function(self):
        """
        :return: вызов функции расчета опорной сетки, автоматическое изменение пути сохранения БД
        """
        self.database_path = self.ui.path_result_db.text()
        module_gdis(self.validate(self.dict_param, self.dict_param), self.database_path)
        self.combobox_scen_switch()

    def table_to_excel(self, path_to_save, list_names):
        """
        Сохранение таблицы/таблиц в Excel файл
        :param path_to_save: путь к БД, сформированной после расчета
        :param list_names: список имен таблиц в БД, откуда необходимо извлечь данные
        :return: запись в Excel
        """
        if self.ui.path_result_db.text() != '':
            path = self.ui.path_result_db.text()
        else:
            path = self.database_path
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
        :return: считывает параметры расчета из виджета и записывает их в БД
        """
        # подключение к БД
        connection = sql.connect(self.database_path)
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
        При нажатии на ячейку в столбце доступном для редактирования открывается возможность редактировать ее значение
        :return: редактирование ячейки пользователем
        """
        # check clicked item of QTreeWidget
        self.ui.treeWidget.itemClicked.connect(self.editable_column)
        # check change in item and update global dictionary of parameters
        self.ui.treeWidget.itemChanged.connect(self.update_dict)

    def combobox_scen_switch(self):
        """
        :return: удаление предыдущих item из combobox переключения сценариев расчета и добавление новых
        """
        # удаление текущих item из combobox
        self.ui.combobox_scenario.clear()

        connection = sql.connect(self.database_path)
        cursor = connection.cursor()
        list_scen = [x[0] for x in
                         cursor.execute('''SELECT name FROM sqlite_master WHERE type='table';''').fetchall() if
                         x[0] != 'parameters' and x[0] != 'report']
        # add combobox items by current calculation
        for scen in list_scen:
            self.ui.combobox_scenario.addItem(scen)

        if list_scen:
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
            self.ui.results.resizeColumnsToContents()
            self.ui.report.setModel(model_report)
            self.ui.report.resizeColumnsToContents()
            self.ui.combobox_scenario.currentTextChanged.connect(self.get_result_table)

    def get_result_table(self, table_name):
        """
        Загрузка и вывод таблиц в виджет
        :param table_name: имя таблицы в БД, откуда необходимо выгрузить данные
        :return: помещает данные из таблицы в БД в виджет окна приложения
        """
        if table_name:
            connection = sql.connect(self.database_path)
            df = pd.read_sql_query(f'SELECT * FROM "{table_name}"', connection)
            df = df.drop(columns=['index'])
            df = df.fillna(0)
            connection.close()

            model = DataframeToTable(df)
            self.ui.results.setModel(model)
            self.ui.results.resizeColumnsToContents()

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
        Считывание всех параметров с виджета для ввода параметров
        :return: словарь с параметрами расчета
        """
        dict_qtreewiget = {}
        list_combobox_items = ['Критерий охвата траектории ГС', 'Учет Q ср. по объекту', 'Учет границ исслед. ННС/ГС',
                               'Учет % от каждого фонда', 'Сценарий расчета', 'Распред-ие ГДИС скв. по годам']
        list_custom_items = ['Файл с данными']
        iterator = QtWidgets.QTreeWidgetItemIterator(self.ui.treeWidget)
        while iterator.value():
            item = iterator.value()
            if item.childCount() == 0:
                if item.text(0) in list_combobox_items:
                    dict_qtreewiget[f'{item.text(0)}'] = self.ui.treeWidget.itemWidget(item, 1).currentText()
                elif item.text(0) in list_custom_items:
                    dict_qtreewiget[f'{item.text(0)}'] = (self.ui.treeWidget.itemWidget(item, 1).layout().
                                                          itemAt(0).widget().text())
                else:
                    dict_qtreewiget[f'{item.text(0)}'] = item.text(1)
            iterator += 1

        return dict_qtreewiget

    def add_combobox(self):
        """
        Добавление виджета ComboBox в Item, где есть только ограниченный выбор параметров расчета
        :return: отредактированные combobox в виджете параметров
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
                continue
            elif name == 'Распред-ие ГДИС скв. по годам':
                combobox.addItem('0')
                combobox.addItem('1')
                combobox.addItem('2')
                self.ui.treeWidget.setItemWidget(current_item, 1, combobox)
                continue
            elif name == 'Критерий охвата траектории ГС':
                combobox.addItem('Да')
                combobox.addItem('Нет')
                self.ui.treeWidget.setItemWidget(current_item, 1, combobox)
                continue
            elif name == 'Учет Q ср. по объекту':
                combobox.addItem('Да')
                combobox.addItem('Нет')
                self.ui.treeWidget.setItemWidget(current_item, 1, combobox)
                continue
            elif name == 'Учет границ исслед. ННС/ГС':
                combobox.addItem('Да')
                combobox.addItem('Нет')
                self.ui.treeWidget.setItemWidget(current_item, 1, combobox)
                continue
            else:
                combobox.addItem('Да')
                combobox.addItem('Нет')
                self.ui.treeWidget.setItemWidget(current_item, 1, combobox)
                continue

    def combobox_actions(self):
        """
        Добавление сигналов на изменение QComboBox параметров расчета
        :return:
        """
        list_combobox_items = ['Критерий охвата траектории ГС', 'Учет Q ср. по объекту', 'Учет границ исслед. ННС/ГС',
                               'Учет % от каждого фонда', 'Сценарий расчета', 'Распред-ие ГДИС скв. по годам']
        for name in list_combobox_items:
            item = self.ui.treeWidget.findItems(name, QtCore.Qt.MatchFlag.MatchContains |
                                                        QtCore.Qt.MatchFlag.MatchRecursive, 0)[0]
            if name == 'Сценарий расчета':
                self.ui.treeWidget.itemWidget(item, 1).currentTextChanged.connect(self.update_dict)
                continue
            elif name == 'Распред-ие ГДИС скв. по годам':
                self.ui.treeWidget.itemWidget(item, 1).currentTextChanged.connect(self.update_dict)
                continue
            elif name == 'Критерий охвата траектории ГС':
                self.ui.treeWidget.itemWidget(item, 1).currentTextChanged.connect(self.update_dict)
                continue
            elif name == 'Учет Q ср. по объекту':
                self.ui.treeWidget.itemWidget(item, 1).currentTextChanged.connect(self.update_dict)
                continue
            elif name == 'Учет границ исслед. ННС/ГС':
                self.ui.treeWidget.itemWidget(item, 1).currentTextChanged.connect(self.update_dict)
                continue
            else:
                self.ui.treeWidget.itemWidget(item, 1).currentTextChanged.connect(self.update_dict)


if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    window = MainWindow()
    window.setWindowTitle('Модуль ОС')
    window.setWindowIcon(QtGui.QIcon('Icon.png'))

    sys.exit(app.exec())
