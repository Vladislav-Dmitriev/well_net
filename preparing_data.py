import os
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
from shapely.geometry import Point, LineString

from functions import get_path


def upload_input_data(dict_names_column, dict_parameters):
    """
    :param dict_names_column: словарь, содержащий названия, в которые переименуются столбцы считанного DataFrame
    :param dict_parameters: словарь с параметрами расчета
    :return: возвращает подготовленный DataFrame после считывания исходного файла со скважинами
    """

    application_path = get_path()
    df_input = pd.read_excel(os.path.join(application_path, dict_parameters['data_file']))
    df_input, date = preparing(dict_names_column, df_input, dict_parameters['min_length_horWell'])

    return df_input, date


def upload_gdis_data(df_input, date, dict_parameters):
    """
    :param df_input: DataFrame, полученный путем считывания исходного файла со скважинами
    :param date: дата выгрузки файла со скважинами
    :param dict_parameters: словарь с параметрами расчета
    :return: функция возвращает исходный DataFrame очищенный от скважин,
             на которых проводились ГДИС не более n лет назад
    """
    application_path = get_path()
    df_gdis = pd.read_excel(os.path.join(application_path, dict_parameters['gdis_file']), skiprows=[0])

    # get preparing dataframes
    df_gdis = gdis_preparing(df_gdis, df_input['wellName'], date, dict_parameters['gdis_option'])

    # drop wells by horizon gdis
    objects = df_gdis.groupby(['wellName'])['workHorizon'].apply(lambda x: set(x.explode()))
    df_input = df_input.apply(lambda x: drop_wells_by_gdis(x, objects), axis=1)
    df_input = df_input[df_input['workHorizon'] != '']

    return df_input


def preparing(dict_names_column, df_input, min_length_horWell):
    """
    Загрузка и подгтовка DataFrame из исходного файла
    :param df_input: DataFrame, полученный из входного файла
    :param min_length_horWell: minimum length between points T1 and T3 to consider the well as horizontal, m
    :param dict_names_column: Имена столбцов для считываемого файла
    :return: Возврат DataFrame, подготовленного к работе(без пропусков данных)
    """
    # rename columns
    df_input.columns = dict_names_column.values()
    df_input = df_input[df_input.workHorizon.notnull()]
    df_input = df_input.fillna(0)

    df_input.wellName = df_input.wellName.astype('str')
    df_input.workHorizon = df_input.workHorizon.astype('str')
    df_input.nameDate = df_input.nameDate.astype('str')
    df_input['nameDate'] = list(map(lambda x: datetime.strptime(x, "%Y-%m-%d"), df_input.nameDate))

    # create a base coordinate for each well
    df_input.loc[df_input["coordinateXT3"] == 0, 'coordinateXT3'] = df_input.coordinateXT1
    df_input.loc[df_input["coordinateYT3"] == 0, 'coordinateYT3'] = df_input.coordinateYT1
    df_input.loc[df_input["coordinateXT1"] == 0, 'coordinateXT1'] = df_input.coordinateXT3
    df_input.loc[df_input["coordinateYT1"] == 0, 'coordinateYT1'] = df_input.coordinateYT3
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

    df_input = df_input[(df_input['workMarker'] != 0) & (df_input['wellStatus'] != 0)]

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
    date = df_input['nameDate'].iloc[0]

    return df_input, date


def gdis_preparing(df_gdis, input_wells, current_date, year):
    """
    Функция очищает DataFrame df_gdis от скважин, на которых ГДИС проводились более n(year) лет назад
    :param df_gdis: данные ГДИС из файла с исследованиями по скважинам, считанные в DataFrame
    :param input_wells: имена всех скважин, входящих в исходный файл со скважинами
    :param current_date: дата выгрузки исходного файла со скважинами
    :param year: опция расчета, задается в годах либо не учитывается
    :return: возвращает DataFrame со скважинами, на которых ГДИС проводились более n(year) лет назад
    """
    dict_names_gdis = {
        'Скважина': 'wellName',
        'Пласты': 'workHorizon',
        'Вид исследования': 'type_of_research',
        'Начальная дата': 'begin_of_research',
        'Дата окончания': 'end_of_research',
        'Оценка': 'quality'
    }

    # HIGH: str = "Высокая"
    # MEDIUM: str = "Хорошая"
    LOW: str = "Низкая"

    df_gdis = df_gdis[['Скважина', 'Пласты', 'Вид исследования', 'Начальная дата', 'Дата окончания', 'Оценка']]
    df_gdis.columns = dict_names_gdis.values()
    df_gdis = df_gdis.fillna(0)
    df_gdis = df_gdis.astype({'wellName': str, 'workHorizon': str, 'quality': str})
    df_gdis = df_gdis[df_gdis['wellName'].isin(input_wells)]
    df_gdis = df_gdis[(df_gdis['end_of_research'] != 0) & (df_gdis['begin_of_research'] != 0)]

    df_gdis['begin_of_research'] = pd.to_datetime(df_gdis['begin_of_research'])
    df_gdis['end_of_research'] = pd.to_datetime(df_gdis['end_of_research'])

    df_gdis['workHorizon'] = list(map(lambda x: x.replace(" ", "").split(";"), df_gdis['workHorizon']))
    df_gdis['type_of_research'] = list(map(lambda x: x.replace(" ", "").split("+"), df_gdis['type_of_research']))
    df_gdis = df_gdis[df_gdis['quality'] != LOW]
    df_gdis['time_of_research'] = df_gdis['end_of_research'] - df_gdis['begin_of_research']
    df_gdis = df_gdis[df_gdis['time_of_research'] != timedelta(0)]
    df_gdis['how_long_ago'] = (current_date - df_gdis['end_of_research']).dt.days // 365  # разница между датой
    # окончания ГДИС и датой выгрузки файла
    df_gdis = df_gdis[(df_gdis['how_long_ago'] >= 0) & (df_gdis['how_long_ago'] <= year)]  # удаление ГДИС, которые
    # начаты после даты выгрузки файла, выделение на которых проводились ГДИС не более заданного кол-ва лет назад
    return df_gdis


def drop_wells_by_gdis(input_row, gdis_objects):
    """
    Функция удаляет объекты для каждой скважины, если по ним проводились ГДИС
    :param input_row: текущая строка из входного DataFrame
    :param gdis_objects: Series из объектов на которых проводились ГДИС, индексами я вляются скважины
    :return: возвращает измененную строку DataFrame или ту же строку, если скважины не оказалось в gdis_object Series
    """
    set_input_objects = set(input_row['workHorizon'].split(', '))
    try:
        set_gdis_objects = gdis_objects[input_row.wellName]
    except KeyError:
        return input_row
    input_row['workHorizon'] = ', '.join(str(e) for e in list(set_input_objects - set_gdis_objects))
    return input_row
