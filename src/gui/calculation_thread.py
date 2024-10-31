from PyQt6 import QtCore
import geopandas as gpd
import pandas as pd
from tqdm import tqdm
from loguru import logger

from src.calculation.support_functions import get_path, delete_logfiles
from src.calculation.calculation_wells import calculation
from src.calculation.shapely_geometry import check_intersection_area, get_contours
from src.input_output.dictionaries import dict_constant
from src.input_output.preparing_data import upload_input_data, preparing_reservoir_properties
from src.input_output.save_database import results_to_db
import warnings
warnings.filterwarnings("ignore", category=RuntimeWarning)
warnings.filterwarnings("ignore", category=FutureWarning)
pd.options.mode.chained_assignment = None  # default='warn'


class CalculationThread(QtCore.QThread):
    progress_signal = QtCore.pyqtSignal(int)
    log_signal = QtCore.pyqtSignal(str)
    finished_signal = QtCore.pyqtSignal()  # Сигнал о завершении расчета
    stop_signal = QtCore.pyqtSignal()  # Сигнал для остановки из внешнего интерфейса

    def __init__(self, dict_parameters, list_name_params, path_database):
        super().__init__()
        self.log_handler = None
        self.dict_parameters = dict_parameters
        self.list_name_params = list_name_params
        self.path_database = path_database
        self._is_stopped = False

    def initialize_logging(self, application_path):
        """Инициализация логов в файл."""
        delete_logfiles(f'{application_path}/output/')
        log_handler = logger.add(
            f'{application_path}/output/logfile.log',
            level='DEBUG',
            format="{time:DD-MM-YYYY HH:mm:ss} {level} {message}",
            rotation='200KB'
        )
        self.log_signal.emit("Начало расчета")
        return log_handler

    def run(self):
        """Основной метод, выполняющий расчет в потоке."""
        application_path = get_path()
        self.log_handler = self.initialize_logging(application_path)

        df_input, df_exceptions, list_exception, path_property = self.load_and_prepare_data()

        # Process contours and wells inside contours
        dict_result, well_out_contour = self.process_contours(df_input, path_property, list_exception)

        # Calculate wells outside contours
        dict_result.update(
            self.process_wells_out_of_contours(df_input, well_out_contour, path_property, list_exception))

        # Save results to database
        self.save_results_to_database(dict_result, df_exceptions)

        self.log_signal.emit("Расчет завершен")
        self.stop()
        self.finished_signal.emit()

    def load_and_prepare_data(self):
        """Загружает и подготавливает данные для расчета."""
        self.log_signal.emit("-----------Чтение и подготовка данных-----------")
        df_input, df_exceptions, list_exception = upload_input_data(dict_constant, self.dict_parameters,
                                                                    self.log_signal, self.progress_signal)
        application_path = get_path()
        path_property = f'{application_path}/input/reservoir_properties.json'

        self.log_signal.emit("Загрузка PVT-свойств из справочника")
        preparing_reservoir_properties(self.dict_parameters, path_property, self.log_signal, self.progress_signal)
        return df_input, df_exceptions, list_exception, path_property

    def process_contours(self, df_input, path_property, list_exception):
        """Обрабатывает контуры и выполняет расчеты."""
        self.log_signal.emit("-----------Расчет опорной сетки по контурам-----------")
        dict_contours = get_contours(f'{get_path()}/input/', self.log_signal, self.progress_signal)

        dict_result = {}
        well_out_contour = set(df_input.wellName.values)

        if not dict_contours:
            self.log_signal.emit("Нет контуров для обработки")
            return dict_result, well_out_contour
        total_contour_count = len(dict_contours)
        self.log_signal.emit(f"Количество контуров: {total_contour_count}")

        for i, (contour_name, contour) in enumerate(tqdm(dict_contours.items(), "Calculation by contours")):

            self.log_signal.emit(f"-----Расчет {i + 1} из {total_contour_count} контуров")
            if not contour.is_valid:
                logger.info(f"Skip self-intersecting contour {contour_name}")
                self.log_signal.emit(f"Пропущен самопересекающийся контур: {contour_name}")
                continue

            wells_in_contour = set(
                check_intersection_area(contour, gpd.GeoDataFrame(df_input, geometry="POINT"),
                                        self.dict_parameters['percent'], self.dict_parameters['calc_option'])
            )

            df_in_contour = df_input[df_input.wellName.isin(wells_in_contour)]
            if df_in_contour[df_in_contour['fond'] != 'ПРОЕКТ'].empty:
                self.log_signal.emit(f"В контуре {contour_name} нет кандидатов для включения в опорную сеть")
                continue

            dict_result.update(calculation(contour, df_in_contour, contour_name, path_property,
                                           list_exception, self.dict_parameters, self.log_signal, self.progress_signal))
            well_out_contour -= wells_in_contour

        return dict_result, well_out_contour

    def process_wells_out_of_contours(self, df_input, well_out_contour, path_property, list_exception):
        """Выполняет расчет для скважин вне контуров."""
        self.log_signal.emit("-----------Расчет опорной сетки вне контуров-----------")
        df_out_contour = df_input[df_input.wellName.isin(well_out_contour)]
        if df_out_contour[df_out_contour['fond'] != 'ПРОЕКТ'].empty:
            return {}

        return calculation(None, df_out_contour, 'Вне контуров', path_property, list_exception,
                           self.dict_parameters, self.log_signal, self.progress_signal)

    def save_results_to_database(self, dict_result, df_exceptions):
        """Сохраняет результаты расчета в базу данных."""
        self.log_signal.emit("-----------Сохранение результатов расчета-----------")
        results_to_db(dict_result, df_exceptions, self.dict_parameters, self.list_name_params, self.path_database,
                      self.progress_signal)
        self.log_signal.emit("Результаты сохранены в базу данных")

    def stop(self):
        self._is_stopped = True
        logger.remove(self.log_handler)
