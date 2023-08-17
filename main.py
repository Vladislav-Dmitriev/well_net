import os
import numpy as np
import pandas as pd
import xlwings as xw
import yaml
from shapely.geometry import Point, LineString
from tqdm import tqdm
import geopandas as gpd
import matplotlib.pyplot as plt

from functions import get_polygon_well, check_intersection_area, check_intersection_point

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

    # Upload files and initial data preparation_________________________________________________________________________

    df_input = pd.read_excel(os.path.join(os.path.dirname(__file__), data_file)).fillna(0)
    # rename columns
    df_input.columns = dict_names_column.values()
    df_input.wellNumberColumn = df_input.wellNumberColumn.astype('str')
    df_input.workHorizon = df_input.workHorizon.astype('str')

    # create a base coordinate for each well

    df_input["length of well T1-3"] = np.sqrt(np.power(df_input.coordinateXT3 - df_input.coordinateXT1, 2)
                                              + np.power(df_input.coordinateYT3 - df_input.coordinateYT1, 2))
    df_input["well type"] = 0
    df_input.loc[df_input["length of well T1-3"] < min_length_horWell, "well type"] = "vertical"
    df_input.loc[df_input["length of well T1-3"] >= min_length_horWell, "well type"] = "horizontal"

    df_input["coordinateX"] = 0
    df_input["coordinateX3"] = 0
    df_input["coordinateY"] = 0
    df_input["coordinateY3"] = 0
    df_input.loc[df_input["well type"] == "vertical", ['coordinateX', 'coordinateX3']] = df_input.coordinateXT1
    df_input.loc[df_input["well type"] == "vertical", ['coordinateY', 'coordinateY3']] = df_input.coordinateYT1
    df_input.loc[df_input["well type"] == "horizontal", 'coordinateX'] = df_input.coordinateXT1
    df_input.loc[df_input["well type"] == "horizontal", 'coordinateX3'] = df_input.coordinateXT3
    df_input.loc[df_input["well type"] == "horizontal", 'coordinateY'] = df_input.coordinateYT1
    df_input.loc[df_input["well type"] == "horizontal", 'coordinateY3'] = df_input.coordinateYT3

    df_input.drop(["length of well T1-3", "coordinateXT1", "coordinateYT1", "coordinateXT3", "coordinateYT3"],
                  axis=1, inplace=True)

    df_prod_wells = df_input.loc[(df_input.workMarker == PROD_MARKER) & (df_input.wellStatus.isin(PROD_STATUS))]
    df_piez_wells = df_input.loc[df_input.wellStatus == PIEZ_STATUS]
    df_inj_wells = df_input.loc[(df_input.workMarker == INJ_MARKER) & (df_input.wellStatus.isin(INJ_STATUS))]
    list_objects = df_prod_wells.workHorizon.str.replace(" ", "").str.split(",").explode().unique()
    list_objects.sort()

    # create dictionary for result
    dict_result = dict.fromkeys(list_objects, 0)

    for horizon in tqdm(list_objects, "calculation for objects"):
        df_result = pd.DataFrame()

        hor_prod_wells = df_prod_wells[list(map(lambda x: len(set(x.replace(" ", "").split(",")) & set([horizon])) > 0,
                                                df_prod_wells.workHorizon))]

        # I. Piezometric wells__________________________________________________________________________________________

        hor_piez_wells = df_piez_wells[list(map(lambda x: len(set(x.replace(" ", "").split(",")) & set([horizon])) > 0,
                                                df_piez_wells.workHorizon))]

        if not hor_piez_wells.empty:

            # add shapely types for well coordinates
            hor_prod_wells.insert(loc=hor_prod_wells.shape[1], column="POINT", value=list(map(lambda x, y: Point(x, y),
                                                                                              hor_prod_wells.coordinateX,
                                                                                              hor_prod_wells.coordinateY)))

            # add POINT3 and LINE columns for horizontal wells
            hor_prod_wells.insert(loc=hor_prod_wells.shape[1], column="POINT3", value=list(map(lambda x, y: Point(x, y),
                                                                                              hor_prod_wells.coordinateX3,
                                                                                              hor_prod_wells.coordinateY3)))

            hor_prod_wells.insert(loc=hor_prod_wells.shape[1], column="LINE", value=list(map(lambda x, y: LineString(tuple(x.coords) + tuple(y.coords)), hor_prod_wells.POINT, hor_prod_wells.POINT3)))

            hor_piez_wells.insert(loc=hor_piez_wells.shape[1], column="POINT", value=list(map(lambda x, y: Point(x, y),
                                                                                              hor_piez_wells.coordinateX,
                                                                                              hor_piez_wells.coordinateY)))

            hor_piez_wells.insert(loc=hor_piez_wells.shape[1], column="POINT3", value=list(map(lambda x, y: Point(x, y),
                                                                                              hor_piez_wells.coordinateX3,
                                                                                              hor_piez_wells.coordinateY3)))

            hor_piez_wells.insert(loc=hor_piez_wells.shape[1], column="LINE", value=list(map(lambda x, y: LineString(tuple(x.coords) + tuple(y.coords)), hor_piez_wells.POINT, hor_piez_wells.POINT3)))

            hor_piez_wells.insert(loc=hor_piez_wells.shape[1], column="AREA",
                                  value=list(map(lambda x: x.buffer(max_distance_piez, join_style=1), hor_piez_wells.LINE)))

            # check_intersection
            hor_piez_wells.insert(loc=hor_piez_wells.shape[1], column="intersection",
                                  value=list(map(lambda x: check_intersection_area(x, hor_prod_wells),
                                                 hor_piez_wells.AREA)))
            hor_piez_wells.insert(loc=hor_piez_wells.shape[1], column="number",
                                  value=list(map(lambda x: len(x), hor_piez_wells.intersection)))
            hor_piez_wells = hor_piez_wells[hor_piez_wells.number > 0]
            hor_prod_wells.insert(loc=hor_prod_wells.shape[1], column="intersection",
                                  value=list(map(lambda x: check_intersection_point(x, hor_piez_wells),
                                                 hor_prod_wells.POINT)))
            hor_prod_wells.insert(loc=hor_prod_wells.shape[1], column="number",
                                  value=list(map(lambda x: len(x), hor_prod_wells.intersection)))

            # !!!OPTIMIZATION!!!
            list_piez_wells = []  # wells that we definitely need
            list_piez_wells += list(hor_prod_wells[hor_prod_wells.number == 1].intersection.explode().unique())
            list_prod_wells = hor_piez_wells[
                hor_piez_wells.wellNumberColumn.isin(list_piez_wells)].intersection.explode().unique()

            df_optim = hor_piez_wells[~hor_piez_wells.wellNumberColumn.isin(list_piez_wells)]
            df_optim.intersection = list(
                map(lambda x: list(set(x).difference(set(list_prod_wells))), df_optim.intersection))
            df_optim.number = list(map(lambda x: len(x), df_optim.intersection))
            df_optim = df_optim[df_optim.number > 0]

            if not df_optim.empty:
                set_visible_wells = set(df_optim.intersection.explode().unique())
                df_optim = df_optim.sort_values(by=['number'], ascending=True)
                for well in df_optim.wellNumberColumn.values:
                    set_exception = set(df_optim[df_optim.wellNumberColumn != well].intersection.explode().unique())
                    if set_exception == set_visible_wells:
                        df_optim = df_optim[df_optim.wellNumberColumn != well]
                list_piez_wells += list(df_optim.wellNumberColumn.values)

            # final list of piezometers to result_df
            df_result = pd.concat([df_result, hor_piez_wells[hor_piez_wells.wellNumberColumn.isin(list_piez_wells)]],
                                           axis=0, sort=False).reset_index(drop=True)

            # wells without communication with piezometer
            isolated_wells = hor_prod_wells[hor_prod_wells.number == 0].wellNumberColumn.values

            hor_prod_wells.drop(["intersection", "number", "POINT", "POINT3"], axis=1, inplace=True)
        else:
            isolated_wells = hor_prod_wells.wellNumberColumn.values

        # II. Injection wells___________________________________________________________________________________________
        if len(isolated_wells):
            hor_prod_wells = hor_prod_wells[hor_prod_wells.wellNumberColumn.isin(isolated_wells)]

            hor_inj_wells = df_inj_wells[
                list(map(lambda x: len(set(x.replace(" ", "").split(",")) & set([horizon])) > 0,
                         df_inj_wells.workHorizon))]

            if not hor_inj_wells.empty:

                # add shapely types for well coordinates
                hor_prod_wells.insert(loc=hor_prod_wells.shape[1], column="POINT",
                                      value=list(map(lambda x, y: Point(x, y),
                                                     hor_prod_wells.coordinateX,
                                                     hor_prod_wells.coordinateY)))
                hor_prod_wells.insert(loc=hor_prod_wells.shape[1], column="POINT3",
                                      value=list(map(lambda x, y: Point(x, y),
                                                     hor_prod_wells.coordinateX3,
                                                     hor_prod_wells.coordinateY3)))

                hor_inj_wells.insert(loc=hor_inj_wells.shape[1], column="POINT",
                                     value=list(map(lambda x, y: Point(x, y),
                                                    hor_inj_wells.coordinateX,
                                                    hor_inj_wells.coordinateY)))
                hor_inj_wells.insert(loc=hor_inj_wells.shape[1], column="POINT3",
                                     value=list(map(lambda x, y: Point(x, y),
                                                    hor_inj_wells.coordinateX3,
                                                    hor_inj_wells.coordinateY3)))
                hor_inj_wells.insert(loc=hor_inj_wells.shape[1], column="AREA",
                                     value=list(map(lambda x, y, x1, y1: get_polygon_well(max_distance_inj, "horizontal", x, y, x1, y1),
                                                    hor_inj_wells.coordinateX, hor_inj_wells.coordinateY,hor_inj_wells.coordinateX3, hor_inj_wells.coordinateY3)))

                # check_intersection
                hor_inj_wells.insert(loc=hor_inj_wells.shape[1], column="intersection",
                                      value=list(map(lambda x: check_intersection_area(x, hor_prod_wells),
                                                     hor_inj_wells.AREA)))
                hor_inj_wells.insert(loc=hor_inj_wells.shape[1], column="number",
                                      value=list(map(lambda x: len(x), hor_inj_wells.intersection)))

                hor_inj_wells = hor_inj_wells[hor_inj_wells.number > 0]

                hor_prod_wells.insert(loc=hor_prod_wells.shape[1], column="intersection",
                                      value=list(map(lambda x: check_intersection_point(x, hor_inj_wells),
                                                     hor_prod_wells.POINT)))
                hor_prod_wells.insert(loc=hor_prod_wells.shape[1], column="number",
                                      value=list(map(lambda x: len(x), hor_prod_wells.intersection)))

                # !!!OPTIMIZATION!!!
                list_inj_wells = []  # wells that we definitely need
                list_inj_wells += list(hor_prod_wells[hor_prod_wells.number == 1].intersection.explode().unique())
                list_prod_wells = hor_inj_wells[
                    hor_inj_wells.wellNumberColumn.isin(list_inj_wells)].intersection.explode().unique()

                df_optim = hor_inj_wells[~hor_inj_wells.wellNumberColumn.isin(list_inj_wells)]
                df_optim.intersection = list(
                    map(lambda x: list(set(x).difference(set(list_prod_wells))), df_optim.intersection))
                df_optim.number = list(map(lambda x: len(x), df_optim.intersection))
                df_optim = df_optim[df_optim.number > 0]

                if not df_optim.empty:
                    set_visible_wells = set(df_optim.intersection.explode().unique())
                    df_optim = df_optim.sort_values(by=['number'], ascending=True)
                    for well in df_optim.wellNumberColumn.values:
                        set_exception = set(df_optim[df_optim.wellNumberColumn != well].intersection.explode().unique())
                        if set_exception == set_visible_wells:
                            df_optim = df_optim[df_optim.wellNumberColumn != well]
                    list_inj_wells += list(df_optim.wellNumberColumn.values)

                # final list of injection to result_df
                df_result = pd.concat(
                    [df_result, hor_inj_wells[hor_inj_wells.wellNumberColumn.isin(list_inj_wells)]],
                    axis=0, sort=False).reset_index(drop=True)

                # wells without communication with injection wells
                isolated_wells = hor_prod_wells[hor_prod_wells.number == 0].wellNumberColumn.values

                hor_prod_wells.drop(["intersection", "number", "POINT", "POINT3"], axis=1, inplace=True)
            else:
                isolated_wells = hor_prod_wells.wellNumberColumn.values

            # III. Single wells_________________________________________________________________________________________
            if len(isolated_wells):
                single_wells = []
                hor_prod_wells = hor_prod_wells[hor_prod_wells.wellNumberColumn.isin(isolated_wells)]

                # add shapely types for well coordinates
                hor_prod_wells.insert(loc=hor_prod_wells.shape[1], column="POINT",
                                      value=list(map(lambda x, y: Point(x, y),
                                                     hor_prod_wells.coordinateX,
                                                     hor_prod_wells.coordinateY)))
                hor_prod_wells.insert(loc=hor_prod_wells.shape[1], column="POINT3",
                                      value=list(map(lambda x, y: Point(x, y),
                                                     hor_prod_wells.coordinateX3,
                                                     hor_prod_wells.coordinateY3)))

                hor_prod_wells.insert(loc=hor_prod_wells.shape[1], column="AREA",
                                      value=list(map(lambda x, y, x1, y1: get_polygon_well(max_distance_single_well,
                                                                                   "horizontal", x, y, x1, y1),
                                                     hor_prod_wells.coordinateX, hor_prod_wells.coordinateY,
                                                     hor_prod_wells.coordinateX3, hor_prod_wells.coordinateY3)))

                # check_intersection
                hor_prod_wells.insert(loc=hor_prod_wells.shape[1], column="intersection",
                                      value=list(map(lambda x, y:
                                                     check_intersection_area(x, hor_prod_wells
                                                     [hor_prod_wells.wellNumberColumn != y]),
                                                     hor_prod_wells.AREA, hor_prod_wells.wellNumberColumn)))
                hor_prod_wells.insert(loc=hor_prod_wells.shape[1], column="number",
                                      value=list(map(lambda x: len(x), hor_prod_wells.intersection)))

                single_wells += list(hor_prod_wells[hor_prod_wells.number == 0].wellNumberColumn)

                df_optim = hor_prod_wells[hor_prod_wells.number > 0]

                # !!!OPTIMIZATION!!!
                if not df_optim.empty:
                    df_optim = df_optim.sort_values(by=['oilRate'], ascending=True)
                    list_wells = df_optim.wellNumberColumn.values
                    while (len(list_wells) != 0) :
                        single_wells += [list_wells[0]]
                        list_exeption = [list_wells[0]] + \
                                        list(df_optim[df_optim.wellNumberColumn == list_wells[0]].intersection.explode().unique())
                        list_wells = [x for x in list_wells if x not in list_exeption]

                    # final list of injection to result_df
                df_result = pd.concat(
                    [df_result, hor_prod_wells[hor_prod_wells.wellNumberColumn.isin(single_wells)]],
                    axis=0, sort=False).reset_index(drop=True)
                dict_result[horizon] = df_result

            else:
                dict_result[horizon] = df_result
                continue
        else:
            dict_result[horizon] = df_result
            continue

    # MAP drawing_______________________________________________________________________________________________________
    fontsize = 6  # Размер шрифта
    size_point = 13
    for key in dict_result.keys():
        hor_prod_wells = df_prod_wells[list(map(lambda x: len(set(x.replace(" ", "").split(",")) & set([key])) > 0,
                                                df_prod_wells.workHorizon))]
        hor_prod_wells.insert(loc=hor_prod_wells.shape[1], column="POINT",
                              value=list(map(lambda x, y: Point(x, y),
                                             hor_prod_wells.coordinateX,
                                             hor_prod_wells.coordinateY)))
        hor_prod_wells.insert(loc=hor_prod_wells.shape[1], column="POINT3",
                              value=list(map(lambda x, y: Point(x, y),
                                             hor_prod_wells.coordinateX3,
                                             hor_prod_wells.coordinateY3)))

        gdf_measuring_wells = gpd.GeoDataFrame(dict_result[key])

        gdf_piez = gdf_measuring_wells.loc[gdf_measuring_wells.wellStatus == PIEZ_STATUS]
        gdf_inj = gdf_measuring_wells.loc[(gdf_measuring_wells.workMarker == INJ_MARKER)
                                          & (gdf_measuring_wells.wellStatus.isin(INJ_STATUS))]
        gdf_prod = gdf_measuring_wells.loc[(gdf_measuring_wells.workMarker == PROD_MARKER)
                                           & (gdf_measuring_wells.wellStatus.isin(PROD_STATUS))]

        ax = gpd.GeoSeries(gdf_piez.AREA).plot(color="plum", figsize=[20, 20])
        # plt.xlim(53*10**4, 54*10**4)
        # plt.ylim(6.7*10**6, 6.72*10**6)

        # area_piez = gdf_piez["AREA"].loc[wellNumberInj].boundary

        gpd.GeoSeries(gdf_prod["AREA"]).plot(ax=ax, color="mistyrose")
        gpd.GeoSeries(gdf_inj["AREA"]).plot(ax=ax, color="azure")

        # Подпись замерных
        for x, y, label in zip(gdf_measuring_wells.coordinateX.values,
                               gdf_measuring_wells.coordinateY.values,
                               gdf_measuring_wells.wellNumberColumn):
            ax.annotate(label, xy=(x, y), xytext=(3, 3), textcoords="offset points", color="red", fontsize=fontsize)
        # Подпись добывающих
        for x, y, label in zip(hor_prod_wells.coordinateX.values,
                               hor_prod_wells.coordinateY.values,
                               hor_prod_wells.wellNumberColumn):
            ax.annotate(label, xy=(x, y), xytext=(3, 3), textcoords="offset points", color="navy", fontsize=fontsize)

        # Точки скважин - черные добывающие, синие треугольники - измеряющие
        gdf_measuring_wells = gdf_measuring_wells.set_geometry(gdf_measuring_wells["POINT"])
        gdf_measuring_wells.plot(ax=ax, color="blue", markersize=size_point, marker="^")
        hor_prod_wells = hor_prod_wells.set_geometry(hor_prod_wells["POINT"])
        hor_prod_wells.plot(ax=ax, color="black", markersize=size_point)
        plt.xlim(53 * 10 ** 4, 54 * 10 ** 4)
        plt.ylim(6.7 * 10 ** 6, 6.72 * 10 ** 6)
        plt.savefig('output/pictures/' + str(key).replace("/", " ") + '.png', dpi=200, quality=100)
        #plt.show()


    # Start print in Excel
    app1 = xw.App(visible=False)
    new_wb = xw.Book()

    for key in dict_result.keys():
        name = str(key).replace("/", " ")
        if f"{name}" in new_wb.sheets:
            xw.Sheet[f"{name}"].delete()
        new_wb.sheets.add(f"{name}")
        sht = new_wb.sheets(f"{name}")
        df = dict_result[key]
        df["intersection"] = list(
                    map(lambda x: " ".join(str(y) for y in x), df["intersection"]))
        del df["POINT"]
        del df["POINT3"]
        del df["AREA"]
        del df["LINE"]
        sht.range('A1').options().value = df

    new_wb.save("output\out_file.xlsx")
    app1.kill()
    # End print
    pass

