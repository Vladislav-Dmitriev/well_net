import sys
import os
import pandas as pd
import sqlite3 as sql
import xlwings as xw
from datetime import datetime
from PyQt6 import QtWidgets, QtCore, QtGui
from src.gui.qtsample import UiMainWindow
from src.gui.validate_widget_data import ValidateData, ValidatePath
from pydantic import ValidationError
from src.calculation.support_functions import get_path
from src.gui.mpl_widget import MplWidget
from src.gui.log_window import LogWindow
from src.gui.calculation_thread import CalculationThread


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
        self.ui = UiMainWindow()  # вызов класса основного окна с базовыми виджетами без функционала
        self.ui.setup_ui(self)  # вызов метода класса, в котором прописано положение и иерархия всех составляющих окна
        self.ui.treeWidget.expandAll()  # раскрытие виджета QTreeWidget, чтобы видеть все задаваемые параметры
        self.filedir_widget()  # добавление внутрь виджета QTreeWidget в item с путем к данным QLineEdit
        self.add_combobox()  # добавление QComboBox на те item QTreeWidget, где параметры задаются всего парой значений
        self.database_path = f'{get_path()}\\wellnet_default.db'  # актуальный путь к БД
        self.set_default_params()  # загрузка в QTreeWidget параметров из БД
        self.dict_param = self.get_dict_qtreewidget()  # словарь с параметрами расчета
        self.filedir_actions()  # валидация пути к файлу + кнопка для открытия диалогового окна выбора файла
        self.combobox_actions()  # обновление словаря с параметрами при изменении значений в одном из QComboBox
        self.combobox_scen_switch()  # QComboBox для переключения между сценариями расчета, загрузка из БД
        self.buttons()  # основные кнопки: расчет, результаты в Excel, выбор директории для записи в БД результатов
        self.item_clicked()  # проверка на нажатие редактируемого item в QTreeWidget
        self.menu_()  # основные кнопки действий меню
        self.log_window = None
        self.calculation_thread = None  # Инициализация для потока расчета
        self.show()
        # self.table_to_excel("Сохранить все сценарии в Excel")

    def set_default_params(self):
        """
        Загрузка параметров из базы данных по умолчанию
        :return: виджет со значениями параметров расчета
        """
        connection = sql.connect(self.database_path)
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
        self.ui.open_project.triggered.connect(self.load_database)

    def load_database(self):
        """
        Загрузка предыдущих расчетов вместе с параметрами
        :return:
        """
        try:
            self.database_path = QtWidgets.QFileDialog.getOpenFileName(self,
                                                                       "Выберите файл с результатами предыдущих расчетов",
                                                                       f'{get_path()}\\output',
                                                                       filter='Database (*.db)')[0]
            self.set_default_params()
            self.combobox_scen_switch()
        except Exception as e:
            pass

    def validate_path_db(self):
        """
        Если пользователь вводит несуществующую директорию, путь формируется автоматически.
        :return: Заполняет поле пути сохранения базы данных после расчета
        """
        try:
            path_save_db = ValidatePath(path=self.ui.path_result_db.text()).path
            # warning delete database if exist
            if os.path.isfile(path_save_db):
                QtWidgets.QMessageBox.about(self, 'Сохранение результатов расчета',
                                            'Внимание! Такой файл уже существует.'
                                            ' Измените путь сохранения результатов или предыдущие'
                                            ' результаты будут удалены при запуске расчета')
            self.ui.path_result_db.setText(path_save_db)
        except ValidationError:
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
            self.message_box(f'Incorrect input parameter: {wrong_param}. {error_message.capitalize()}')
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
        self.ui.calculate.clicked.connect(lambda: self.main_calc_function())

        # save current table in Excel
        self.ui.save_table.clicked.connect(lambda: self.table_to_excel(self.ui.save_table.text()))
        # save all tables in Excel
        self.ui.save_all_tables.clicked.connect(lambda: self.table_to_excel(self.ui.save_all_tables.text()))
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
        Запуск окна логов и функции расчета в отдельных потоках
        """
        if not os.path.isfile(self.dict_param['Файл с данными']):
            return self.message_box("По указанному пути файл с данными не найден")

        self.setDisabled(True)

        self.database_path = self.ui.path_result_db.text()

        # Создание и запуск потока
        self.calculation_thread = CalculationThread(self.validate(self.dict_param, self.dict_param),
                                                    list(self.dict_param.keys()), self.database_path)

        # Создание окна логов, подключение к сигналам
        self.log_window = LogWindow(self.calculation_thread, self)
        self.log_window.stop_button.setDisabled(False)
        self.calculation_thread.log_signal.connect(self.log)
        self.calculation_thread.finished_signal.connect(self.on_calculation_finished)
        self.calculation_thread.stop_signal.connect(self.on_calculation_stopped)

        # Запуск потока и отображение окна логов
        self.calculation_thread.start()
        self.log_window.show()

    def log(self, message):
        if self.log_window:
            self.log_window.log_area.append(f"{datetime.now().strftime("%Y-%m-%d %H-%M-%S")}  {message}")

    def on_calculation_stopped(self):
        self.setDisabled(False)
        self.calculation_thread.stop()
        self.log("Расчет остановлен.")
        self.calculation_thread = None  # Обнуляем поток для возможности перезапуска

    def on_calculation_finished(self):
        # self.log("Расчет завершен.")
        self.setEnabled(True)  # Разблокируем кнопку запуска
        self.combobox_scen_switch()
        self.calculation_thread = None  # Обнуляем поток для возможности перезапуска

    def table_to_excel(self, button_text):
        """
        Сохранение таблицы/таблиц в Excel файл
        :return: запись в Excel
        """
        path_to_save = QtWidgets.QFileDialog.getSaveFileName(self, "Сохранение таблицы опорной сетки",
                                                             f'{get_path()}\\output\\{os.getlogin()}_'
                                                             f'{datetime.now().strftime("%Y-%m-%d %H-%M-%S")}.xlsx',
                                                             filter='Excel (*.xlsx *.xls)')[0]
        if not path_to_save:
            # Если пользователь отменил сохранение
            return

        connection = sql.connect(self.database_path)

        app1 = xw.App(visible=False)
        new_wb = xw.Book()

        try:
            if button_text == 'Сохранить все сценарии в Excel':
                calc_scripts = [self.ui.combobox_scenario.itemText(i) for i in range(self.ui.combobox_scenario.count())] + [
                    "report"]
                for script in calc_scripts:
                    df = pd.read_sql_query(f'SELECT * FROM "{script}"', connection)
                    df = df.drop(columns=['index'])
                    if script != 'report':
                        df = df.drop(columns=['GEOMETRY', 'AREA', 'polygon'])
                        df = df.fillna(0)
                        df = df[((df['Объект расчета'] != 0) & (
                                    df['Объект расчета'] == self.ui.combobox_horizon.currentText())) | (
                                        (df['Объект расчета'] == 0) & (
                                        (df['Объекты работы'].str.contains(self.ui.combobox_horizon.currentText())) |
                                        (df['Объекты работы'] == 0)))].reset_index(drop=True)
                    new_wb.sheets.add(f"{script.replace('/', '_')}")
                    sht = new_wb.sheets(f"{script.replace('/', '_')}")
                    sht.range('A1').options(pd.DataFrame, index=False).value = df

            else:
                df = pd.read_sql_query(f'SELECT * FROM "{self.ui.combobox_scenario.currentText()}"', connection)
                df = df.drop(columns=['index', 'polygon', 'AREA', 'GEOMETRY'])
                df = df.fillna(0)
                df = df[((df['Объект расчета'] != 0) & (df['Объект расчета'] == self.ui.combobox_horizon.currentText())) | (
                        (df['Объект расчета'] == 0) & (
                         (df['Объекты работы'].str.contains(self.ui.combobox_horizon.currentText())) |
                         (df['Объекты работы'] == 0)))].reset_index(drop=True)
                new_wb.sheets.add(f"{self.ui.combobox_scenario.currentText().replace('/', '_')}")
                sht = new_wb.sheets(f"{self.ui.combobox_scenario.currentText().replace('/', '_')}")
                sht.range('A1').options(pd.DataFrame, index=False).value = df
            new_wb.save(path_to_save)

        finally:
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

    def clear_layout(self, layout):
        """
        Удаление текущей картинки, чтобы разместить новую
        :return:
        """
        while layout.count() > 0:
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()  # Корректное удаление виджета
            else:
                self.clear_layout(item.layout())  # Если это layout, рекурсивно очищаем

    @staticmethod
    def rounding(df):
        """
        Метод возвращает округленные значения в DataFrame
        :param df: DataFrame сводки по сценариям или результат текущего сценария
        :return:
        """
        if df.columns[0] == '№ скважины':
            list_rounding_result = ['Координата X', 'Координата забоя Х (по траектории)', 'Координата Y',
                                    'Координата забоя Y (по траектории)', 'Дебит нефти (ТР), т/сут',
                                    'Дебит природного газа, тыс.м3/сут', 'Приемистость (ТР), м3/сут',
                                    'Обводненность (ТР), % (объём)', 'Дебит конденсата газа, т/сут',
                                    'Средний радиус по объекту, м', 'Коэффициент для расчета времени исследования',
                                    'Проницаемость, мД', 'Начальное пластовое давление (карты изобар), атм',
                                    'Время исследования, сут', 'Потери нефти, т', 'Потери газа, тыс. м3',
                                    'Потери закачки, м3', 'Процент охвата площади объекта',
                                    'Доля пьезометров в опорной сети', 'Доля нагнетательных в опорной сети',
                                    'Доля добывающих в опорной сети', 'Доля газовых добывающих скважин в опорной сети',
                                    'Средний дебит нефти по объекту, т/сут']
            df[list_rounding_result] = df[list_rounding_result].round(2)
            return df
        else:
            list_rounding_report = ['Средний радиус', 'Среднее время исследования', 'Потери нефти 1 год, т',
                                    'Потери нефти 2 год, т', 'Потери нефти 3 год, т',
                                    'Потери закачки жидкости 1 год, м3', 'Потери закачки жидкости 2 год, м3',
                                    'Потери закачки жидкости 3 год, м3', 'Потери по добыче газа 1 год, тыс.м3',
                                    'Потери по добыче газа 2 год, тыс.м3', 'Потери по добыче газа 3 год, тыс.м3']
            df[list_rounding_report] = df[list_rounding_report].round(2)
            return df

    def combobox_scen_switch(self):
        """
        :return: удаление предыдущих item из combobox переключения сценариев расчета и добавление новых
        """
        # удаление текущих item из combobox
        self.ui.combobox_scenario.clear()
        connection = sql.connect(self.database_path)
        cursor = connection.cursor()
        list_scripts = [x[0] for x in
                        cursor.execute('''SELECT name FROM sqlite_master WHERE type='table';''').fetchall() if
                        x[0] != 'parameters' and x[0] != 'report']
        # add combobox items by current calculation
        for sc in list_scripts:
            self.ui.combobox_scenario.addItem(sc)

        if list_scripts:
            df = pd.read_sql_query(f'SELECT * FROM "{list_scripts[0]}"', connection)
            df_report = pd.read_sql_query(f'SELECT * FROM "report"', connection)
            df = df.fillna(0)
            list_horizons = sorted(list(set(df[df['Объект расчета'] != 0]['Объект расчета'].explode())))
            df = df.drop(columns=['index'])
            for hor in list_horizons:
                self.ui.combobox_horizon.addItem(hor)
            self.clear_layout(self.ui.tab_2.layout())
            df = df[((df['Объект расчета'] != 0) & (df['Объект расчета'] == self.ui.combobox_horizon.currentText())) | (
                        (df['Объект расчета'] == 0) & (
                            (df['Объекты работы'].str.contains(self.ui.combobox_horizon.currentText())) | (
                                df['Объекты работы'] == 0)))].reset_index(drop=True)
            self.ui.tab_2.layout().addWidget(MplWidget(df.copy(), self.dict_param['Сценарий расчета']))

            df = df.drop(columns=['polygon', 'GEOMETRY', 'AREA'])
            df = self.rounding(df)
            df_report = df_report.drop(columns=['index'])
            df_report = df_report.fillna(0)
            df_report = self.rounding(df_report)
            model = DataframeToTable(df)
            model_report = DataframeToTable(df_report)
            self.ui.results.setModel(model)
            self.ui.results.resizeColumnsToContents()
            self.ui.report.setModel(model_report)
            self.ui.report.resizeColumnsToContents()
            self.ui.combobox_scenario.currentTextChanged.connect(self.get_result_table)
            self.ui.combobox_horizon.currentTextChanged.connect(self.get_filtered_table)
        connection.close()

    def get_result_table(self, table_name):
        """
        Загрузка и вывод таблиц в виджет
        :param table_name: имя таблицы в БД, откуда необходимо выгрузить данные
        :return: помещает данные из таблицы в БД в виджет окна приложения
        """
        if table_name:
            connection = sql.connect(self.database_path)
            df = pd.read_sql_query(f'SELECT * FROM "{table_name}"', connection)
            connection.close()

            df = df.drop(columns=['index'])
            df = df.fillna(0)

            self.ui.combobox_horizon.clear()
            list_horizons = sorted(list(set(df[df['Объект расчета'] != 0]['Объект расчета'].explode())))
            for hor in list_horizons:
                self.ui.combobox_horizon.addItem(hor)

            df = df[((df['Объект расчета'] != 0) & (df['Объект расчета'] == self.ui.combobox_horizon.currentText())) | (
                        (df['Объект расчета'] == 0) & (
                            (df['Объекты работы'].str.contains(self.ui.combobox_horizon.currentText())) | (
                                df['Объекты работы'] == 0)))].reset_index(drop=True)

            self.clear_layout(self.ui.tab_2.layout())
            self.ui.tab_2.layout().addWidget(MplWidget(df.copy(), self.dict_param['Сценарий расчета']))
            df = df.drop(columns=['polygon', 'GEOMETRY', 'AREA'])
            df = self.rounding(df)
            model = DataframeToTable(df)
            self.ui.results.setModel(model)
            self.ui.results.resizeColumnsToContents()

    def get_filtered_table(self, horizon):
        """
        Фильтр для таблицы результатов расчета по определенному объекту
        :param horizon: объект, выбранный пользователем
        :return:
        """
        table_name = self.ui.combobox_scenario.currentText()
        if table_name:
            connection = sql.connect(self.database_path)
            df = pd.read_sql_query(f'SELECT * FROM "{table_name}"', connection)
            connection.close()
            df = df.drop(columns=['index'])
            df = df.fillna(0)
            df = df[((df['Объект расчета'] != 0) & (df['Объект расчета'] == horizon)) | ((df['Объект расчета'] == 0) & (
                        (df['Объекты работы'].str.contains(self.ui.combobox_horizon.currentText())) | (
                            df['Объекты работы'] == 0)))].reset_index(drop=True)

            self.clear_layout(self.ui.tab_2.layout())
            self.ui.tab_2.layout().addWidget(MplWidget(df.copy(), self.dict_param['Сценарий расчета']))
            df = df.drop(columns=['polygon', 'GEOMETRY', 'AREA'])
            df = self.rounding(df)
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

    def closeEvent(self, event):
        if self.log_window is not None:
            self.log_window.close()
        event.accept()
