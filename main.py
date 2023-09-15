import os
import pandas as pd
import yaml
from loguru import logger
import geopandas as gpd
from shapely.geometry import Point, Polygon
from functions import write_to_excel, load_contour, get_time_coef
from preparing_data import preparing
from calculation_wells import calc_contour
import warnings

warnings.filterwarnings('ignore')
pd.options.mode.chained_assignment = None  # default='warn'

dict_names_column = {
    '№ скважины': 'wellName',
    'Дата': 'nameDate',
    'Характер работы': 'workMarker',
    "Состояние": 'wellStatus',
    'Объекты работы': 'workHorizon',
    "Координата X": 'coordinateXT1',
    "Координата Y": 'coordinateYT1',
    "Координата забоя Х (по траектории)": 'coordinateXT3',
    "Координата забоя Y (по траектории)": 'coordinateYT3',
    'Дебит нефти (ТР), т/сут': 'oilRate'}

# CONSTANT
dict_constant = { 'PROD_STATUS': ["РАБ.", "Б/Д ТГ", "НАК"],
                                    'PROD_MARKER' : "НЕФ",
                                    'PIEZ_STATUS': "ПЬЕЗ",
                                    'INJ_MARKER': "НАГ",
                                    'INJ_STATUS': ["РАБ."]}

if __name__ == '__main__':
    # Parameters
    with open('conf_files/parameters.yml', encoding='UTF-8') as f:
        dict_parameters = yaml.safe_load(f)
    data_file = dict_parameters['data_file']
    # maximum distance between wells, m
    max_distance = dict_parameters['max_distance']
    # minimum length between points T1 and T3 to consider the well as horizontal, m
    min_length_horWell = dict_parameters['min_length_horWell']
    # get preparing dataframes
    df_input = preparing(dict_names_column, data_file, min_length_horWell)
    # path to file with properties for current object
    logger.info("Checking for properties")
    property_path = 'conf_files/reservoir_properties.yml'
    logger.info(f"path:{property_path}")
    # path to folder with contours
    logger.info("CHECKING FOR CONTOURS")
    dir_path = os.path.dirname(os.path.realpath(__file__))
    logger.info(f"path:{dir_path}")
    logger.info("check the content of contours")

    contours_path = dir_path + "\\contours"
    contours_content = os.listdir(path=contours_path)
    # словарь для записи резульатов по контурам
    dict_result = {}
    # список коэффициентов на средний радиус охвата


    well_out_contour = set(df_input.wellName.values)

    if contours_content:
        logger.info(f"contours: {len(contours_content)}")
        for contour in contours_content:
            contour_name = contour.replace(".txt", "")
            contour_path = contours_path + f"\\{contour}"
            polygon = load_contour(contour_path)
            df_points = gpd.GeoDataFrame(df_input, geometry="POINT")
            wells_in_contour = set(df_points[df_points.intersects(polygon)].wellName)
            df_input_contour = df_input[df_input.wellName.isin(wells_in_contour)]
            if df_input_contour.empty:
                continue
            df_result_all = calc_contour(df_input_contour, polygon, contour_name,
                                         max_distance, property_path, **dict_constant)
            dict_result[contour_name] = df_result_all
            well_out_contour = well_out_contour.difference(wells_in_contour)

    else:
        logger.info("No contours!")
        contour_name = 'out_contour'

    polygon = None
    df_out_contour = df_input[df_input.wellName.isin(well_out_contour)]

    if not df_out_contour.empty:
        # расчет для скважин вне контура
        df_result_all = calc_contour(df_out_contour, polygon, contour_name,
                                     property_path, max_distance, **dict_constant)
        dict_result["out_contour"] = df_result_all

    # Start print in Excel
    write_to_excel(dict_result)
    pass
