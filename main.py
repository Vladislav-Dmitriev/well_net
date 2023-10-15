import os
import warnings

import geopandas as gpd
import pandas as pd
from loguru import logger

from calculation_wells import calc_contour
from functions import write_to_excel, load_contour, check_intersection_area, unpack_status, upload_parameters
from mapping import visualization
from preparing_data import upload_input_data, upload_gdis_data

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
    'Дебит нефти (ТР), т/сут': 'oilRate',
    'Приемистость (ТР), м3/сут': 'injectivity'}

# CONSTANT
dict_constant = {'PROD_STATUS': ["РАБ.", "Б/Д ТГ", "НАК"],
                 'PROD_MARKER': "НЕФ",
                 'PIEZ_STATUS': "ПЬЕЗ",
                 'INJ_MARKER': "НАГ",
                 'INJ_STATUS': ["РАБ."]}

if __name__ == '__main__':
    # Upload parameters
    dict_parameters = upload_parameters('conf_files/parameters.yml')

    # Upload files and initial data preparation_________________________________________________________________________
    df_input, date = upload_input_data(dict_names_column, dict_parameters)
    df_input = df_input.iloc[1500:4500, :]  # выделение DataFrame меньшего размера для проверки

    # Upload files and GDIS data preparation____________________________________________________________________________
    if (dict_parameters['gdis_option'] is not None) and (dict_parameters['gdis_file'] is not None):
        df_input = upload_gdis_data(df_input, date, dict_parameters)

    # path to file with properties for current object
    logger.info("Checking for properties")
    path_property = 'conf_files/reservoir_properties.yml'
    logger.info(f"path:{path_property}")

    # path to folder with contours
    logger.info("CHECKING FOR CONTOURS")
    dir_path = os.path.dirname(os.path.realpath(__file__))
    logger.info(f"path:{dir_path}")
    logger.info("check the content of contours")

    # get path and names of contour files with coordinates
    contours_path = dir_path + "\\contours"
    contours_content = os.listdir(path=contours_path)

    well_out_contour = set(df_input.wellName.values)
    dict_result = {}
    list_wells_in_contour = []

    if contours_content:
        logger.info(f"contours: {len(contours_content)}")
        for contour in contours_content:
            contour_name = contour.replace(".txt", "")
            contour_path = contours_path + f"\\{contour}"
            polygon = load_contour(contour_path)
            df_points = gpd.GeoDataFrame(df_input, geometry="POINT")
            wells_in_contour = set(check_intersection_area(polygon, df_points,
                                                           dict_parameters['percent'], calc_option=True))
            list_wells_in_contour += [wells_in_contour]
            df_in_contour = df_input[df_input.wellName.isin(wells_in_contour)]
            if df_in_contour.empty:
                continue
            dict_result.update(calc_contour(dict_parameters['separation_by_years'],
                                            dict_parameters['limit_radius_coef'], polygon, df_in_contour,
                                            contour_name, dict_parameters['max_distance'], path_property,
                                            dict_parameters['mult_coef'], dict_parameters['percent'],
                                            dict_parameters['verticalWellAngle'],
                                            dict_parameters['MaxOverlapPercent'], dict_parameters['angle_horizontalT1'],
                                            dict_parameters['angle_horizontalT3'], **dict_constant))
            well_out_contour = well_out_contour.difference(wells_in_contour)

    else:
        logger.info("No contours!")

    polygon = None
    df_out_contour = df_input[df_input.wellName.isin(well_out_contour)]

    if not df_out_contour.empty:
        contour_name = 'out_contour'
        # расчет для скважин вне контура
        dict_result.update(calc_contour(dict_parameters['separation_by_years'], dict_parameters['limit_radius_coef'],
                                        polygon, df_out_contour, contour_name, dict_parameters['max_distance'],
                                        path_property, dict_parameters['mult_coef'], dict_parameters['percent'],
                                        dict_parameters['verticalWellAngle'],
                                        dict_parameters['MaxOverlapPercent'], dict_parameters['angle_horizontalT1'],
                                        dict_parameters['angle_horizontalT3'], **dict_constant))

    # MAP drawing_______________________________________________________________________________________________________
    PROD_STATUS, PROD_MARKER, PIEZ_STATUS, INJ_MARKER, INJ_STATUS = unpack_status(dict_constant)
    df_input_prod = df_input.loc[(df_input.workMarker == PROD_MARKER)
                                 & (df_input.wellStatus.isin(PROD_STATUS))]
    visualization(df_input_prod, dict_parameters['percent'], dict_result, **dict_constant)
    # Start print in Excel
    write_to_excel(dict_result, **dict_constant)
    pass
