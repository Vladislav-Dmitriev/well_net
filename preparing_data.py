import os
import numpy as np
import pandas as pd
from shapely.geometry import Point, LineString
import geopandas as gpd


def preparing(dict_names_column, data_file, min_length_horWell):
    '''
    Загрузка и подгтовка DataFrame из исходного файла
    :param min_length_horWell: minimum length between points T1 and T3 to consider the well as horizontal, m
    :param dict_names_column: Имена столбцов для считываемого файла
    :param data_file: Путь к расположению файла
    :return: Возврат DataFrame, подготовленного к работе(без пропусков данных)
    '''
    # Upload files and initial data preparation_________________________________________________________________________
    df_input = pd.read_excel(os.path.join(os.path.dirname(__file__), data_file))
    # rename columns
    df_input.columns = dict_names_column.values()
    df_input = df_input[df_input.workHorizon.notnull()]
    df_input = df_input.fillna(0)

    df_input.wellName = df_input.wellName.astype('str')
    df_input.workHorizon = df_input.workHorizon.astype('str')

    # create a base coordinate for each well
    df_input.loc[df_input["coordinateXT3"] == 0, 'coordinateXT3'] = df_input.coordinateXT1
    df_input.loc[df_input["coordinateYT3"] == 0, 'coordinateYT3'] = df_input.coordinateYT1
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

    # add to input dataframe columns for shapely types of coordinates

    df_input.insert(loc=df_input.shape[1], column="POINT", value=list(map(lambda x, y: Point(x, y),
                                                                          df_input.coordinateX,
                                                                          df_input.coordinateY)))

    df_input.insert(loc=df_input.shape[1], column="POINT3", value=list(map(lambda x, y: Point(x, y),
                                                                           df_input.coordinateX3,
                                                                           df_input.coordinateY3)))
    df_input.insert(loc=df_input.shape[1], column="GEOMETRY", value=0)
    df_input["GEOMETRY"] = df_input["GEOMETRY"].where(df_input["well type"] != "vertical",
                                                      list(map(lambda x: x, df_input.POINT)))
    df_input["GEOMETRY"] = df_input["GEOMETRY"].where(df_input["well type"] != "horizontal",
                                                      list(map(lambda x, y: LineString(
                                                          tuple(x.coords) + tuple(y.coords)),
                                                               df_input.POINT, df_input.POINT3)))

    return df_input
