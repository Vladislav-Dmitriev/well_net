import warnings
from tqdm import tqdm

import geopandas as gpd
import pandas as pd
from loguru import logger

from src.calculation.support_functions import get_path, delete_logfiles
from src.calculation.calculation_wells import calculation
from src.calculation.shapely_geometry import check_intersection_area, get_contours
from src.input_output.dictionaries import dict_constant
from src.input_output.preparing_data import upload_input_data, preparing_reservoir_properties
from src.input_output.save_database import results_to_db

warnings.filterwarnings('ignore')
pd.options.mode.chained_assignment = None  # default='warn'


def module_gdis(dict_parameters, list_name_params, path_database):
    """
    Основная функция расчета, автоматически подбирает кандидатов в опорную сетку и записывает результаты в БД
    :param dict_parameters: словарь с параметрами расчета
    :param list_name_params: список имен параметров для пользователя
    :param path_database: путь к базе данных для записи в нее результатов после завершения расчета
    :return:
    """
    # path to application
    application_path = get_path()
    # delete previous logfiles
    delete_logfiles(f'{application_path}\\output\\')
    # add logs to file
    log_handler = logger.add(f'{application_path}\\output\\logfile.log', level='DEBUG',
                             format="{time:DD-MM-YYYY HH:mm:ss} {level} {message}", rotation='200KB',
                             filter=lambda record: "USER" not in record["extra"])
    logger.info("Starting calculation")
    logger.bind(USER=True).info("Начало расчета")

    # Upload data, initial data preparation_____________________________________________________________________________
    df_input, df_exceptions, list_exception = upload_input_data(dict_constant, dict_parameters)

    # path to file with properties for current object
    logger.info("Checking for properties")
    path_property = f'{application_path}\\input\\reservoir_properties.json'
    logger.info(f"path: {path_property}")

    # Upload and print reservoir_properties.yml
    logger.bind(USER=True).info("Загрузка PVT-свойств из справочника")
    preparing_reservoir_properties(dict_parameters, path_property)

    # path to folder with contours
    logger.info("CHECKING FOR CONTOURS")
    logger.info(f"path: {application_path}")
    logger.info("Сheck the content of contours")
    # get path and names of contour files with coordinates
    contours_path = application_path + "\\input\\"
    dict_contours = get_contours(contours_path)

    well_out_contour = set(df_input.wellName.values)
    dict_result = {}
    list_wells_in_contour = []

    if dict_contours.keys():
        # calculation well inside contour
        logger.info(f"Count of contours: {len(dict_contours)}")
        for contour in tqdm(dict_contours.keys(), "Построение опорной сетки по контурам"):
            df_points = gpd.GeoDataFrame(df_input, geometry="POINT")
            if dict_contours[contour].is_valid:
                wells_in_contour = set(check_intersection_area(dict_contours[contour], df_points,
                                                               dict_parameters['percent'], dict_parameters['calc_option']))
            else:
                logger.info(f'WARNING! Self-intersecting polygon of contour: {contour}. Contour skipped!')
                continue
            list_wells_in_contour += [wells_in_contour]
            df_in_contour = df_input[df_input.wellName.isin(wells_in_contour)]
            if df_in_contour[df_in_contour['fond'] != 'ПРОЕКТ'].empty:
                continue

            dict_result.update(calculation(dict_contours[contour], df_in_contour, contour, path_property,
                                           list_exception, dict_parameters))
            well_out_contour = well_out_contour.difference(wells_in_contour)

    else:
        logger.info("No contours!")

    polygon = None  # no contours
    df_out_contour = df_input[df_input.wellName.isin(well_out_contour)]

    if not df_out_contour[df_out_contour['fond'] != 'ПРОЕКТ'].empty:
        contour_name = 'Вне контуров'
        logger.info("Calculation wells out of contours")
        # calculation wells out contour
        dict_result.update(calculation(polygon, df_out_contour, contour_name, path_property,
                                       list_exception, dict_parameters))

    # Results___________________________________________________________________________________________________________
    results_to_db(dict_result, df_exceptions, dict_parameters, list_name_params, path_database)

    logger.info("End of calculation")
    logger.remove(log_handler)
    pass
