import os
import numpy as np
import pandas as pd
import yaml
from shapely.geometry import Polygon
from tqdm import tqdm
from loguru import logger
import geopandas as gpd

from mapping import visualisation
from preparing_data import preparing
from calculation_wells import piez_calc, inj_calc, single_calc
from shapely.geometry import LineString, Point, Polygon
from functions import write_to_excel

from functions import check_intersection_area, optimization, intersect_number
from mapping import visualisation
from preparing_data import preparing
from calculation_wells import piez_calc, inj_calc, single_calc, calc_without_contour
import xlwings as xw

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
PROD_MARKER: str = "НЕФ"
PROD_STATUS = ["РАБ.", "Б/Д ТГ", "НАК"]

PIEZ_STATUS: str = "ПЬЕЗ"

INJ_MARKER: str = "НАГ"
INJ_STATUS = ["РАБ."]

if __name__ == '__main__':
    # Parameters
    with open('conf_files/parameters.yml', encoding='UTF-8') as f:
        dict_parameters = yaml.safe_load(f)
    data_file = dict_parameters['data_file']
    max_distance_piez = dict_parameters['max_distance_piez']
    max_distance_inj = dict_parameters['max_distance_inj']
    min_length_horWell = dict_parameters['min_length_horWell']
    max_distance_single_well = dict_parameters['max_distance_single_well']
    distance = [max_distance_piez, max_distance_inj, min_length_horWell, max_distance_single_well]


    # get preparing dataframes
    df_input = preparing(dict_names_column, data_file, distance)

    # create dictionary for result
    # dict_result = dict.fromkeys(list_objects, 0)

    logger.info("CHECKING FOR CONTOURS")

    dir_path = os.path.dirname(os.path.realpath(__file__))
    logger.info(f"path:{dir_path}")

    contours_path = dir_path + "\\contours"
    contours_content = os.listdir(path=contours_path)

    logger.info("check the content of contours")

    well_out_contour = set(df_input.wellNumberColumn.values)

    app1 = xw.App(visible=False)
    new_wb = xw.Book()

    if contours_content:
        logger.info(f"contours: {len(contours_content)}")
        for contour in contours_content:
            contour_name = contour.replace(".txt", "")
            contour_path = contours_path + f"\\{contour}"
            columns_name = ['coordinateX', 'coordinateY']
            cont = pd.read_csv(contour_path, sep=' ', decimal=',', header=0, names=columns_name)
            df_contour = gpd.GeoDataFrame(cont)
            list_of_coord = [[x, y] for x, y in zip(df_contour.coordinateX, df_contour.coordinateY)]
            polygon = Polygon(list_of_coord)

            df_points = gpd.GeoDataFrame(df_input, geometry="POINT")
            wells_in_contour = set(df_input[df_points.intersects(polygon)].wellNumberColumn)
            df_input_contour = df_input[df_input.wellNumberColumn.isin(wells_in_contour)]

            df_prod_wells = df_input_contour.loc[
                (df_input.workMarker == PROD_MARKER) & (df_input.wellStatus.isin(PROD_STATUS))]
            df_piez_wells = df_input_contour.loc[df_input.wellStatus == PIEZ_STATUS]
            df_inj_wells = df_input_contour.loc[
                (df_input.workMarker == INJ_MARKER) & (df_input.wellStatus.isin(INJ_STATUS))]
            list_objects = df_input_contour.workHorizon.str.replace(" ", "").str.split(",").explode().unique()
            list_objects.sort()

            df_result_all = pd.DataFrame()

            for horizon in tqdm(list_objects, "calculation for objects"):
                df_result = pd.DataFrame()

                hor_prod_wells = df_prod_wells[list(map(lambda x: len(set(x.replace(" ", "").split(",")) & set([horizon])) > 0,
                                                        df_prod_wells.workHorizon))]

                # I. Piezometric wells__________________________________________________________________________________________

                isolated_wells, hor_piez_wells, hor_prod_wells, df_result = piez_calc(horizon, df_piez_wells,
                                                                                                hor_prod_wells,
                                                                                                df_result)
                df_result_all = pd.concat([df_result_all, df_result], axis=0, sort=False).reset_index(drop=True)

                # II. Injection wells___________________________________________________________________________________________
                if len(isolated_wells):
                    isolated_wells, hor_prod_wells, df_inj_wells, df_result = inj_calc(horizon, isolated_wells,
                                                                                                hor_prod_wells,
                                                                                                df_inj_wells,
                                                                                                df_result)

                    # III. Single wells_________________________________________________________________________________________
                    if len(isolated_wells):
                        single_wells, hor_prod_wells, df_optim, df_result = single_calc(horizon, isolated_wells,
                                                                                                 hor_prod_wells,
                                                                                                 df_result)
                    else:
                        df_result_all = pd.concat([df_result_all, df_result], axis=0, sort=False).reset_index(drop=True)
                        df_result_all.drop_duplicates(subset=['wellNumberColumn'])
                        continue
                else:
                    df_result_all = pd.concat([df_result_all, df_result], axis=0, sort=False).reset_index(drop=True)
                    df_result_all.drop_duplicates(subset=['wellNumberColumn'])
                    continue


            # MAP drawing_______________________________________________________________________________________________________
            visualisation(polygon, contour_name, df_result_all, df_prod_wells, 6, 13, PROD_MARKER, PROD_STATUS,
                                                                          PIEZ_STATUS, INJ_MARKER, INJ_STATUS)

            well_out_contour = well_out_contour.difference(wells_in_contour)

            # объединение result для всех пластов одного контура !!!

        # save to xls - на один лист для одного котура
        # Start print in Excel
        write_to_excel(new_wb, df_result_all, contour_name)
        write_to_excel(new_wb, df_result_all, contour_name)
    else:
        logger.info("No contours!")

    # расчет для скважин вне контура
    df_out_contour = df_input[df_input.wellNumberColumn.isin(well_out_contour)]

    df_prod_wells = df_out_contour.loc[(df_out_contour.workMarker == PROD_MARKER) & (df_out_contour.wellStatus.isin(PROD_STATUS))]
    df_piez_wells = df_out_contour.loc[df_out_contour.wellStatus == PIEZ_STATUS]
    df_inj_wells = df_out_contour.loc[(df_out_contour.workMarker == INJ_MARKER) & (df_out_contour.wellStatus.isin(INJ_STATUS))]
    list_objects = df_out_contour.workHorizon.str.replace(" ", "").str.split(",").explode().unique()
    list_objects.sort()

    # create dataframe for calculation wells without contour
    df_result_all = pd.DataFrame()

    for horizon in tqdm(list_objects, "calculation objects"):
        df_result = pd.DataFrame()
        df_result_all = calc_without_contour(horizon, df_prod_wells, df_piez_wells, df_inj_wells, df_result, df_result_all)
        # MAP drawing (карта для одного объекта одного контура)____________________________________________________
        visualisation(horizon, df_result_all, df_prod_wells, 6, 13, PROD_MARKER, PROD_STATUS, PIEZ_STATUS, INJ_MARKER,
                      INJ_STATUS)

        well_out_contour = well_out_contour.differense(wells_in_contour)


        # объединение result для всех пластов одного контура !!!

        # save to xls - на один лист для одного контура
        # Start print in Excel

        write_to_excel(new_wb, df_result_all, contour_name)

        new_wb.save("output\out_file.xlsx")
        app1.kill()
        # End print
        pass




