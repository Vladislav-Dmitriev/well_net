from pydantic import field_validator, BaseModel, ValidationError, Field
from typing import Union
from loguru import logger
import pandas as pd
import os


class ValidatePath(BaseModel):
    path: str = Field(..., description='path')

    @field_validator('path')
    def validate_path(cls, path: str) -> str:
        dir_path, file_name = os.path.split(path)

        # Validate if the directory exists and file has a '.db' extension
        if os.path.isdir(dir_path) and file_name.endswith('.db'):
            return path
        else:
            # Construct a default path if the validation fails
            raise ValueError('Wrong save results path')


class ValidateData(BaseModel):

    data_file: str = Field(..., description='data_file')
    calculation_scenario: str = Field(..., description='calculation_scenario')
    gdis_option: str = Field(..., description='gdis_option')
    calc_option: bool = Field(..., description='calc_option')
    percent: float = Field(..., description='percent')
    horizon_count: float = Field(..., description='horizon_count')
    mult_coef: list = Field(..., description='mult_coef')
    limit_radius_coef: float = Field(..., description='limit_radius_coef')
    min_length_horWell: float = Field(..., description='min_length_horWell')
    water_cut: Union[float, str] = Field(..., description='water_cut')
    fluid_rate: Union[float, str] = Field(..., description='fluid_rate')
    mean_oilrate_option: bool = Field(..., description='mean_oilrate_option')
    percent_oilrate: float = Field(..., description='percent_oilrate')
    limit_oilrate: Union[float, str] = Field(..., description='limit_oilrate')
    limit_research_time: bool = Field(..., description='limit_research_time')
    min_research_time: Union[float, str] = Field(..., description='min_research_time')
    max_research_time: Union[float, str] = Field(..., description='max_research_time')
    option_percent: bool = Field(..., description='option_percent')
    list_order_fond: str = Field(..., description='list_order_fond')
    percent_piez: float = Field(..., description='percent_piez')
    percent_inj: float = Field(..., description='percent_inj')
    percent_prod: float = Field(..., description='percent_prod')
    separation_by_years: int = Field(..., description='separation_by_years')
    max_distance: float = Field(..., description='max_distance')
    verticalWellAngle: float = Field(..., description='verticalWellAngle')
    MaxOverlapPercent: float = Field(..., description='MaxOverlapPercent')
    angle_horizontalT1: float = Field(..., description='angle_horizontalT1')
    angle_horizontalT3: float = Field(..., description='angle_horizontalT3')

    @field_validator('data_file')
    def filename(cls, data_file: str) -> str:
        """
        Валидация пути к файлу с данными и типа файла
        :param data_file: путь к файлу с данными в строковом виде
        :return:
        """
        dir_path, file_name = os.path.split(data_file)
        if os.path.isdir(dir_path) and file_name.endswith('.xlsx') and os.path.isfile(data_file):
            return data_file
        else:
            logger.info("Wrong path to data file or file format")
            raise ValueError('Wrong path to data file or file format. Expected .xlsx format.')

    @field_validator('calculation_scenario')
    def scenario(cls, calculation_scenario: str) -> str:
        """
        Валидация выбранного сценария расчета
        :param calculation_scenario: строка с названием сценария из QComboBox
        :return:
        """
        if calculation_scenario == 'Оптимальная сетка':
            return 'optimize'
        else:
            return 'regular'

    @field_validator('gdis_option', mode='before')
    def gdis_date(cls, gdis_option: str) -> str:
        """
        Валидация даты последнего актуального исследования ГДИС
        :param gdis_option: дата последнего актуального исследования ГДИС в виде строки из виджета
        :return:
        """
        try:
            pd.to_datetime(gdis_option, format='%d.%m.%Y')
            return gdis_option
        except ValidationError:
            logger.info("Incorrect GDIS date format")
            raise ValidationError('Enter correct format of GDIS date')

    @field_validator( 'calc_option', 'mean_oilrate_option', 'limit_research_time', 'option_percent', mode='before')
    def check_boolean_options(cls, value: str) -> bool:
        """
        Валидация параметров, имеющих значения да/нет, то есть boolean
        :param value: строковое значение параметра из QComboBox
        :return:
        """
        if value == 'Да':
            return True
        else:
            return False

    @field_validator('percent', 'percent_oilrate', 'percent_piez', 'percent_inj', 'percent_prod',
                     'MaxOverlapPercent', mode='before')
    def string_to_percent(cls, percent_val: str) -> float:
        """
        Валидация параметров, определяющихся в процентах. Перевод в число с плавающей точкой
        :param percent_val: строковое значение параметров из виджета
        :return:
        """
        try:
            percent_val = float(percent_val)
            if (percent_val >= 0) and (percent_val <= 100):
                return percent_val
            else:
                logger.info('Value is out of bounds (0, 100)')
                raise ValueError('Enter a numeric value in the range 0-100')
        except ValueError:
            logger.info('Percent is not in range of acceptable values')
            raise ValueError('Enter a numeric value in the range 0-100')

    @field_validator('horizon_count', mode='before')
    def horizon_count_to_int(cls, horizon_count: str) -> float:
        """
        Валидация параметра кол-ва объектов работы на скважину
        :param horizon_count: строковое значение параметра кол-ва объектов работы на скважину
        :return:
        """
        try:
            float(horizon_count)
            if str(horizon_count).isdigit():
                return float(horizon_count)
            else:
                raise ValueError('Value must be positive integer')
        except ValueError:
            logger.info('Value must be positive integer')
            raise ValueError('Value must be positive integer')

    @field_validator('fluid_rate', 'limit_oilrate', 'min_research_time', 'max_research_time', mode='before')
    def str_to_empty_or_float(cls, str_to_float_empty: str):
        """
        Валидация параметров, ограничивающих попадание скважин на расчет модуля: дебит жидкости,
        :param str_to_float_empty: строковое значение параметра
        :return:
        """
        try:
            str_to_float_empty = float(str_to_float_empty)
            if str_to_float_empty >= 0:
                return str_to_float_empty
            else:
                logger.info('Value must be positive')
                raise ValueError('Value must be positive')
        except ValueError:
            if str_to_float_empty.strip() == '':
                str_to_float_empty = str_to_float_empty.strip()
                return str_to_float_empty
            else:
                logger.info('Value must be positive')
                raise ValueError('Value must be positive')

    @field_validator('water_cut', mode='before')
    def watercut_to_float(cls, water_cut: str) -> float:
        """
        Валидация значения параметра обводненности
        :param water_cut: строковое значение параметра из виджета
        :return:
        """
        try:
            water_cut = float(water_cut)
            if (water_cut >= 0) and (water_cut <= 100):
                return water_cut
            else:
                logger.info('Value is out of bounds 0-100')
                raise ValueError('Enter a numeric value in the range 0-100')
        except ValueError:
            if water_cut == '':
                return water_cut
            else:
                logger.info('Percent is not in range of acceptable values')
                raise ValueError('Enter a numeric value in the range 0-100')

    @field_validator('mult_coef', mode='before')
    def correct_mult_coef(cls, mult_coef: str) -> list[float]:
        """
        Валидация списка коэффициентов на средний радиус исследования
        :param mult_coef: строковое значение списка коэффициентов из виджета
        :return:
        """
        mult_coef = mult_coef.split(',')
        try:
            mult_coef = [float(x) for x in mult_coef if float(x) > 0]
            if len(mult_coef) > 0:
                return mult_coef
            else:
                raise ValueError('Wrong type of coefficients')
        except ValueError:
            logger.info(f'Wrong type of coefficients')
            raise ValueError('Wrong type of coefficients')

    @field_validator('limit_radius_coef', 'min_length_horWell', 'max_distance', 'verticalWellAngle',
                     'angle_horizontalT1', 'angle_horizontalT3', mode='before')
    def limit_coef(cls, float_params: str) -> float:
        """
        Валидация параметров, имеющих значение в виде числа с плавающей точкой
        :param float_params: строковые значения параметров с плавающей запятой из виджета
        :return:
        """
        try:
            float_params = float(float_params)
            if float_params > 0:
                return float_params
            else:
                logger.info('Value must be positive')
                raise ValueError('Value must be positive')
        except TypeError:
            logger.info(f'Wrong type of parameter {float_params}')
            raise TypeError(f'Wrong type of parameter {float_params}')

    @field_validator('separation_by_years', mode='before')
    def check_separation(cls, separation_by_years: str) -> int:
        """
        Валидация параметра распределения исследования по года в слепых зонах
        :param separation_by_years: значение combobox в формате строки
        :return: целое число
        """
        return int(separation_by_years)

