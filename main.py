import os
import pandas as pd
import yaml
from loguru import logger
import geopandas as gpd
from shapely.geometry import Polygon
from functions import write_to_excel
from preparing_data import preparing
from calculation_wells import calc_contour
import warnings

warnings.filterwarnings('ignore')
pd.options.mode.chained_assignment = None  # default='warn'

dict_names_column = {
    '№ скважины': 'wellNumberColumn',
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

    # get preparing dataframes
    df_input = preparing(dict_names_column, data_file, max_distance_piez=dict_parameters['max_distance_piez'],
                         max_distance_inj=dict_parameters['max_distance_inj'],
                         min_length_horWell=dict_parameters['min_length_horWell'],
                         max_distance_single_well=dict_parameters['max_distance_single_well'])

    logger.info("CHECKING FOR CONTOURS")

    dir_path = os.path.dirname(os.path.realpath(__file__))
    logger.info(f"path:{dir_path}")

    contours_path = dir_path + "\\contours"
    contours_content = os.listdir(path=contours_path)
    dict_result = {}

    logger.info("check the content of contours")

    well_out_contour = set(df_input.wellNumberColumn.values)

    if contours_content:
        logger.info(f"contours: {len(contours_content)}")
        for contour in contours_content:
            contour_name = contour.replace(".txt", "")
            contour_path = contours_path + f"\\{contour}"
            columns_name = ['coordinateX', 'coordinateY']
            df_contour = pd.read_csv(contour_path, sep=' ', decimal=',', header=0, names=columns_name)
            gdf_contour = gpd.GeoDataFrame(df_contour)
            list_of_coord = [[x, y] for x, y in zip(gdf_contour.coordinateX, gdf_contour.coordinateY)]
            polygon = Polygon(list_of_coord)
            df_points = gpd.GeoDataFrame(df_input, geometry="POINT")
            wells_in_contour = set(df_input[df_points.intersects(polygon)].wellNumberColumn)
            df_input_contour = df_input[df_input.wellNumberColumn.isin(wells_in_contour)]
            if df_input_contour.empty:
                continue

            df_result_all, df_prod_wells = calc_contour(df_input_contour, polygon, contour_name, **dict_constant)
            dict_result[contour_name] = df_result_all
            well_out_contour = well_out_contour.difference(wells_in_contour)

    else:
        logger.info("No contours!")
        contour_name = 'out_contour'

    polygon = None
    df_out_contour = df_input[df_input.wellNumberColumn.isin(well_out_contour)]

    if not df_out_contour.empty:
        # расчет для скважин вне контура
        df_result_all, df_prod_wells = calc_contour(df_out_contour, polygon, contour_name, **dict_constant)
        dict_result["out_contour"] = df_result_all

    # Start print in Excel
    write_to_excel(dict_result)
    pass
