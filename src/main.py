import os
import time
import warnings

import geopandas as gpd
import pandas as pd
from loguru import logger

from src.calculation.auxiliary_functions import upload_parameters, get_path
from src.calculation.calculation_wells import calculation
from src.calculation.geometry import check_intersection_area, load_contour
from src.preparing.dictionaries import dict_constant
from src.preparing.preparing_data import upload_input_data, preparing_reservoir_properties
from src.visualization.mapping import mesh_visualization, visualization
from src.visualization.print_in_excel import write_optim_mesh, write_regular_mesh

warnings.filterwarnings('ignore')
pd.options.mode.chained_assignment = None  # default='warn'


def module_gdis():
    # Upload parameters
    dict_parameters = upload_parameters('input/parameters.yml')

    # Upload data, initial data preparation_____________________________________________________________________________
    df_input, list_exception = upload_input_data(dict_constant, dict_parameters)

    # add logs to file
    logger.add('output/logfile.log', level='INFO', format="{message}")
    logger.info("Starting calculation")
    # path to file with properties for current object
    logger.info("Checking for properties")
    path_property = 'input/reservoir_properties.json'
    logger.info(f"path: {path_property}")

    # Upload and print reservoir_properties.yml
    preparing_reservoir_properties(dict_parameters, path_property)

    # path to folder with contours
    logger.info("CHECKING FOR CONTOURS")
    application_path = get_path()
    logger.info(f"path: {application_path}")
    logger.info("check the content of contours")

    # get path and names of contour files with coordinates
    contours_path = application_path + "\\input"
    # contours_content = os.listdir(path=contours_path)
    contours_content = [f for f in os.listdir(path=contours_path) if f.endswith('.txt')]

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

            dict_result.update(calculation(polygon, df_in_contour, contour_name, path_property,
                                           list_exception, dict_parameters))
            well_out_contour = well_out_contour.difference(wells_in_contour)

    else:
        logger.info("No contours!")

    polygon = None
    df_out_contour = df_input[df_input.wellName.isin(well_out_contour)]

    if not df_out_contour.empty:
        contour_name = 'out_contour'
        # расчет для скважин вне контура
        dict_result.update(calculation(polygon, df_out_contour, contour_name, path_property,
                                       list_exception, dict_parameters))

    # Results___________________________________________________________________________________________________________
    if dict_parameters['calculation_scenario'] == 'optimize':
        # Map drawing for optimize mesh scenario
        df_input_prod = df_input.loc[(df_input['fond'] == 'ДОБ') | (df_input['fond'] == 'ПРОЕКТ')]
        visualization(df_input_prod, dict_result, dict_parameters['percent'], dict_parameters['mean_oilrate_option'])
        # Start print in Excel
        write_optim_mesh(df_input, dict_result, dict_parameters['percent'],
                         dict_parameters['calc_option'], **dict_constant)
    else:
        # Map drawing for regular mesh scenario
        mesh_visualization(df_input, dict_result, list_exception,
                           dict_parameters['percent'], dict_parameters['mean_oilrate_option'])
        # Start print in Excel
        write_regular_mesh(df_input, dict_result, dict_parameters['percent'], dict_parameters['calc_option'],
                           **dict_constant)

    logger.info("End of calculation")

    time.sleep(10)

    pass
