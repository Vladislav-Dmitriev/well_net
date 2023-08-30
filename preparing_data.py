import os
import numpy as np
import pandas as pd
import yaml
from shapely.geometry import Point, LineString
import geopandas as gpd

from functions import get_polygon_well

def preparing(dict_names_column, data_file, distance):
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
    df_input.loc[df_input["length of well T1-3"] < distance[2], "well type"] = "vertical"
    df_input.loc[df_input["length of well T1-3"] >= distance[2], "well type"] = "horizontal"

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
    df_input_ver = df_input[df_input["well type"] == "vertical"]
    df_input_hor = df_input[df_input["well type"] == "horizontal"]
    df_input_ver.insert(loc=df_input_ver.shape[1], column="GEOMETRY", value=list(map(lambda x: x, df_input_ver.POINT)))
    df_input_hor.insert(loc=df_input_hor.shape[1], column="GEOMETRY", value=list(map(lambda x, y: LineString(tuple(x.coords) + tuple(y.coords)),
                                                                                     df_input_hor.POINT, df_input_hor.POINT3)))

    df_input_ver.insert(loc=df_input_ver.shape[1], column="AREA",
                        value=list(map(lambda x, y: get_polygon_well(distance[0], "vertical", x, y),
                                       df_input_ver.coordinateX, df_input_ver.coordinateY)))
    df_input_hor.insert(loc=df_input_hor.shape[1], column="AREA", value=list(map(lambda x, y, x1, y1:
                                                                                 get_polygon_well(distance[0],
                                                                                "horizontal", x, y, x1, y1),
                                                                                 df_input_hor.coordinateX,
                                                                                 df_input_hor.coordinateY,
                                                                                 df_input_hor.coordinateX3,
                                                                                 df_input_hor.coordinateY3)))
    df_input = pd.concat([df_input_ver, df_input_hor], axis=0, sort=False).reset_index(drop=True)
    return df_input