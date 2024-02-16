import os
import warnings

import geopandas as gpd
import pandas as pd
from loguru import logger

from calculation_wells import calc_contour
from dictionaries import dict_constant
from functions import upload_parameters, get_path
from geometry import check_intersection_area, load_contour
from mapping import mesh_visualization
from preparing_data import upload_input_data, upload_gdis_data, preparing_reservoir_properties
from print_in_excel import write_cluster_mesh
from wells_clustering import calc_regular_mesh

warnings.filterwarnings('ignore')
pd.options.mode.chained_assignment = None  # default='warn'

if __name__ == '__main__':

    # Upload parameters
    dict_parameters = upload_parameters('conf_files/parameters.yml')

    # Upload files and initial data preparation_________________________________________________________________________
    df_input, date, list_exception = upload_input_data(dict_constant, dict_parameters)

    # Upload files and GDIS data preparation____________________________________________________________________________
    if (dict_parameters['gdis_option'] is not None) and (
            pd.to_datetime(dict_parameters['gdis_option'], format='%d.%m.%Y') < date) and (
            dict_parameters['gdis_file'] is not None):
        df_input = upload_gdis_data(df_input, date, dict_parameters)

    # add logs to file
    logger.add('output/logfile.log', level='INFO', format="{message}")
    logger.info("Starting calculation")
    # path to file with properties for current object
    logger.info("Checking for properties")
    path_property = 'conf_files/reservoir_properties.json'
    logger.info(f"path: {path_property}")

    # Upload and print reservoir_properties.yml
    preparing_reservoir_properties(dict_parameters, path_property)

    # path to folder with contours
    logger.info("CHECKING FOR CONTOURS")
    application_path = get_path()
    logger.info(f"path: {application_path}")
    logger.info("check the content of contours")

    # get path and names of contour files with coordinates
    contours_path = application_path + "\\contours"
    contours_content = os.listdir(path=contours_path)

    well_out_contour = set(df_input.wellName.values)
    dict_result = {}
    dict_mesh = {}
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

            dict_result.update(calc_contour(polygon, df_in_contour, contour_name, path_property,
                                            list_exception, dict_parameters, **dict_constant))
            well_out_contour = well_out_contour.difference(wells_in_contour)

    else:
        logger.info("No contours!")

    polygon = None
    df_out_contour = df_input[df_input.wellName.isin(well_out_contour)]

    if not df_out_contour.empty:
        contour_name = 'out_contour'
        # расчет для скважин вне контура
        dict_mesh.update(calc_regular_mesh(df_out_contour, dict_parameters, contour_name))
        mesh_visualization(df_out_contour, dict_mesh)
        # dict_result.update(calc_contour(polygon, df_out_contour, contour_name, path_property,
        #                                 list_exception, dict_parameters, **dict_constant))

    # # MAP drawing_______________________________________________________________________________________________________
    # PROD_STATUS, PROD_MARKER, PIEZ_STATUS, INJ_MARKER, INJ_STATUS, DELETE_STATUS = unpack_status(dict_constant)
    # df_input_prod = df_input.loc[df_input['fond'] == 'ДОБ']
    # visualization(df_input_prod, dict_parameters['percent'], dict_result)
    # # Start print in Excel
    # write_to_excel(dict_parameters['percent'], df_input, dict_result, **dict_constant)
    write_cluster_mesh(dict_mesh)
    logger.info("End of calculation")

    pass
