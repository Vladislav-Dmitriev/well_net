from pydantic import field_validator, ValidationError
from typing_extensions import TypedDict
from loguru import logger
import pandas as pd


class ValidatorData(TypedDict):

    data_file: str
    calculation_scenario: str
    gdis_option: str
    calc_option: str
    percent: str
    horizon_count: str
    mult_coef: str
    limit_radius_coef: str
    min_length_horWell: str
    water_cut: str
    fluid_rate: str
    mean_oilrate_option: str
    percent_oilrate: str
    limit_oilrate: str
    limit_research_time: str
    min_research_time: str
    max_research_time: str
    option_percent: str
    list_order_fond: str
    percent_piez: str
    percent_inj: str
    percent_prod: str
    separation_by_years: str
    max_distance: str
    verticalWellAngle: str
    MaxOverlapPercent: str
    angle_horizontalT1: str
    angle_horizontalT3: str

    # validation file format
    @field_validator('data_file')
    def filename(cls, data_file: str) -> str:
        if '.xlsx' in data_file:
            return data_file
        else:
            logger.info(f'Wrong input file format: {data_file}')
            raise ValueError('Wrong input file format')

    # selected scenario
    @field_validator('calculation_scenario')
    def scenario(cls, calculation_scenario: str) -> str:
        if calculation_scenario.lower() == 'оптимальная сетка':
            calculation_scenario = 'optimize'
            return calculation_scenario
        else:
            calculation_scenario = 'regular'
            return calculation_scenario

    # check GDIS date
    @field_validator('gdis_option')
    def gdis_date(cls, gdis_option: str) -> str:
        try:
            pd.to_datetime(gdis_option, format='%d.%m.%Y')
            return gdis_option
        except ValueError:
            logger.info("Incorrect GDIS date format")
            raise ValueError('Enter correct format of GDIS date')

    # check calc_option status
    @field_validator('str_to_boolean', 'option_percent', 'calc_option', 'mean_oilrate_option', 'limit_research_time')
    def check_boolean_options(cls, str_to_boolean: str) -> bool:
        if str_to_boolean.lower() == 'да':
            str_to_boolean = True
            return str_to_boolean
        else:
            str_to_boolean = False
            return str_to_boolean

    # validate percent parameters
    @field_validator('percent_val', 'percent', 'percent_oilrate', 'percent_piez', 'percent_inj', 'percent_prod',
                     'MaxOverlapPercent')
    def string_to_percent(cls, percent_val: str) -> float:
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

    @field_validator('horizon_count')
    def horizon_count_to_int(cls, horizon_count: str) -> float:
        try:
            float(horizon_count)
            if str(horizon_count).isdigit():
                return float(horizon_count)
            else:
                raise ValueError('Value must be positive integer')
        except ValueError:
            logger.info('Value must be positive integer')
            raise ValueError('Value must be positive integer')

    @field_validator('str_to_float_empty', 'fluid_rate', 'limit_oilrate', 'min_research_time',
                     'max_research_time')
    def str_to_empty_or_float(cls, str_to_float_empty: str):
        try:
            str_to_float_empty = float(str_to_float_empty)
            if str_to_float_empty >= 0:
                return str_to_float_empty
            else:
                logger.info('Value must be positive')
                raise ValueError('Value must be positive')
        except ValidationError:
            if str_to_float_empty.strip() == '':
                str_to_float_empty = str_to_float_empty.strip()
                return str_to_float_empty
            else:
                logger.info('Value must be positive')
                raise ValidationError('Value must be positive')

    @field_validator('water_cut')
    def watercut_to_float(cls, water_cut: str) -> float:
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

    # check mult coefficients
    @field_validator('mult_coef')
    def correct_mult_coef(cls, mult_coef: str) -> list[float]:
        mult_coef = mult_coef.split(',')
        try:
            mult_coef = [float(x) for x in mult_coef if float(x) > 0]
            if len(mult_coef) > 0:
                return mult_coef
            else:
                raise TypeError('Wrong type of coefficients')
        except TypeError:
            logger.info(f'Wrong type of coefficients')
            raise TypeError('Wrong type of coefficients')

    # validation of limit radius coefficient
    @field_validator('float_params', 'limit_radius_coef', 'min_length_horWell', 'max_distance', 'verticalWellAngle',
                     'angle_horizontalT1', 'angle_horizontalT3')
    def limit_coef(cls, float_params: str) -> float:
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

    # validation count of years for separation GDIS
    @field_validator('separation_by_years')
    def check_separation(cls, separation_by_years: str) -> int:
        return int(separation_by_years)

