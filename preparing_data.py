import json
import os
import sys
from datetime import timedelta

import numpy as np
import pandas as pd
from loguru import logger
from shapely.geometry import Point, LineString

from dictionaries import dict_geobd_columns, dict_names_column
from functions import get_path, clean_work_horizon, unpack_status, exception_marker


def upload_input_data(dict_constant, dict_parameters):
    """
    Считывание файла с исключенными скважинами, затем загрузка данных,
    их подготовка к расчету в зависимости от базы данных
    и удаление исключенных скважин

    :param dict_constant: словарь со статусами работы скважин
    :param dict_parameters: словарь с параметрами расчета
    :return: возвращает подготовленный DataFrame после считывания исходного файла со скважинами
    """

    # Upload exception list wells
    list_exception = []
    if dict_parameters['exception_file'] is not None:
        list_exception += get_exception_wells(dict_parameters)

    application_path = get_path()
    logger.info("Data type definition")

    # с новой выгрузкой NGT 'utf-8' не всегда может считать, поэтому добавил try/except
    try:
        first_row = pd.read_csv(os.path.join(application_path, dict_parameters['data_file']), header=None, sep=';',
                                encoding='utf-8', nrows=1)
        use_encoding = 'utf-8'
    except UnicodeDecodeError:
        first_row = pd.read_csv(os.path.join(application_path, dict_parameters['data_file']), header=None, sep=';',
                                encoding='cp1251', nrows=1)
        use_encoding = 'cp1251'
    # first_row = pd.read_excel(os.path.join(application_path, dict_parameters['data_file']), header=None, nrows=1)
    if first_row.loc[0][0] == '№ скважины':
        # base = 'NGT'
        logger.info("Preparing NGT data")

        df = pd.read_csv(os.path.join(application_path, dict_parameters['data_file']), header=0, sep=';',
                         encoding=use_encoding, decimal='.')
        df_input = preprocessing_NGT(df, dict_parameters['min_length_horWell'])  # предобработка данных из NGT
        df_input, date = preparing(dict_constant, df_input,
                                   dict_parameters['horizon_count'], dict_parameters['water_cut'],
                                   dict_parameters['fluid_rate'], list_exception)

    elif first_row.loc[0][0] == 'NSKV':
        # base = 'GeoBD'

        logger.info("Preparing GeoBD data")

        df = pd.read_csv(os.path.join(application_path, dict_parameters['data_file']), header=0, sep=';',
                         encoding='cp1251', decimal='.', skiprows=[1])
        df_input = preprocessing_GeoBD(df, dict_constant, dict_geobd_columns)
        df_input, date = preparing(dict_constant, df_input, dict_parameters['horizon_count'],
                                   dict_parameters['water_cut'], dict_parameters['fluid_rate'], list_exception)
    else:
        print('Формат загруженного файла не подходит для модуля')
        sys.exit()
    return df_input, date, list_exception


def preprocessing_GeoBD(df_input, dict_constant, dict_geobd_columns):
    """
    Подготовка данных ГеоБД

    :param df_input: Выгрузка данных ГеоБД
    :param dict_constant: статусы и характеры работы скважин
    :param dict_geobd_columns: список имен столбцов
    :return: DataFrame с необходимыми столбцами для расчета, столбцы в правильном порядке,
    скважины разделены на ННС и ГС
    """

    PROD_STATUS, PROD_MARKER, PIEZ_STATUS, INJ_MARKER, INJ_STATUS, DELETE_MARKER = unpack_status(dict_constant)

    df_input = df_input.fillna(0)
    df_input = df_input[df_input.PLAST.notnull()]
    df_input = df_input[df_input.KUST.notnull()]
    df_input = df_input[df_input['KUST'] != 0]
    df_input = df_input[df_input['SOST'] != 0]
    df_input[['NSKV', 'PLAST', 'STATUS_DATE']] = df_input[['NSKV', 'PLAST', 'STATUS_DATE']].astype('str')

    # cleaning wellStatus
    df_input = df_input.loc[~df_input.SOST.map(str.lower).str.contains(DELETE_MARKER)]

    df_input = df_input[(df_input['PEREV'] == 'совмест.') | (df_input['PEREV'] == 'работает')]
    df_input = df_input.reset_index(drop=True)

    df_input['MEST'] = list(str(df_input.loc[0]['LINK']).split('='))[-1].upper()
    df_input['X3'] = 0
    df_input['Y3'] = 0
    required_cols = ['NSKV', 'UWI', 'STATUS_DATE', 'FOND', 'SOST', 'MEST', 'PLAST', 'PEREV', 'KUST', 'X', 'X3',
                     'Y', 'Y3', 'DEBOIL', 'DEBLIQ', 'PRIEM', 'VPROCOBV', 'SPOSOB', 'DEBGAS', 'PRIEMGAS', 'DEBCOND']
    df_input = df_input[required_cols]

    list_well_names = list(df_input['UWI'].explode().unique())  # список уникальных названий скважин
    df_input = df_input.sort_values(by=['NSKV'], ascending=True)
    df_input.reset_index(drop=True)
    df_input['well type'] = ''
    for well in list_well_names:
        objs = list(
            df_input[df_input['UWI'] == well].PLAST.explode().unique())  # список уникальных объектов месторождения
        if len(set(df_input[df_input['UWI'] == well].NSKV)) > 1:  # если в столбце имен скважин уникальных больше 1,
            # но у них одинаковая кодировка, то это горизонтальная скважина
            df_input.loc[df_input['UWI'] == well, 'well type'] = 'horizontal'
            df_input.loc[df_input['UWI'] == well, 'VPROCOBV'] = \
                list(df_input.loc[df_input['UWI'] == well, 'VPROCOBV'].explode())[0]
            coord_x = list(df_input[df_input['UWI'] == well].X.explode().unique())
            coord_y = list(df_input[df_input['UWI'] == well].Y.explode().unique())
            df_input.loc[df_input['UWI'] == well, 'X'] = coord_x[0]
            df_input.loc[df_input['UWI'] == well, 'X3'] = coord_x[-1]
            df_input.loc[df_input['UWI'] == well, 'Y'] = coord_y[0]
            df_input.loc[df_input['UWI'] == well, 'Y3'] = coord_y[-1]

        else:
            df_input.loc[df_input['UWI'] == well, 'well type'] = 'vertical'
            df_input.loc[df_input['UWI'] == well, 'VPROCOBV'] = \
                list(df_input.loc[df_input['UWI'] == well, 'VPROCOBV'].explode())[0]
            coord_x = list(df_input[df_input['UWI'] == well].X.explode().unique())
            coord_y = list(df_input[df_input['UWI'] == well].Y.explode().unique())
            df_input.loc[df_input['UWI'] == well, 'X'] = coord_x[0]
            df_input.loc[df_input['UWI'] == well, 'X3'] = coord_x[0]
            df_input.loc[df_input['UWI'] == well, 'Y'] = coord_y[0]
            df_input.loc[df_input['UWI'] == well, 'Y3'] = coord_y[0]

        df_input.loc[df_input['UWI'] == well, 'PLAST'] = df_input.apply(lambda x: ', '.join(objs), axis=1)

    df_input.reset_index(drop=True)
    df_input = df_input.drop_duplicates(subset=['UWI'])
    df_input = df_input.reset_index(drop=True)

    df_input.drop(columns=['UWI', 'PEREV'], axis=1, inplace=True)
    correct_order = ['NSKV', 'STATUS_DATE', 'FOND', 'SOST', 'MEST', 'PLAST', 'KUST', 'X', 'X3',
                     'Y', 'Y3', 'DEBOIL', 'DEBLIQ', 'DEBGAS', 'PRIEM', 'PRIEMGAS', 'VPROCOBV', 'SPOSOB', 'DEBCOND',
                     'well type']

    df_input = df_input[correct_order]
    df_input.columns = dict_geobd_columns.values()
    # нужно перевести столбец приемистости по газу 'injectivity_day' в м3/сут как в NGT, а в ГеоБД этот столбец в тыс. м3/сут
    df_input['injectivity_day'] = df_input['injectivity_day'] * 1000

    return df_input


def preprocessing_NGT(df_input, min_length_horWell):
    """
    Подготовка данных из NGT

    :param min_length_horWell: минимальная длина ГС, для разделения скважин на ННС и ГС
    :param df_input: Выгрузка данных NGT
    :return: подготовленный DataFrame выгрузки NGT, скважины разделены на ННС и ГС
    """

    # rename columns
    df_input.columns = dict_names_column.values()

    # cleaning null values
    df_input = df_input[df_input.workHorizon.notnull()]
    df_input = df_input[df_input.wellCluster.notnull()]
    df_input = df_input.fillna(0)

    # transfer to string type
    df_input[['wellName', 'workHorizon', 'nameDate', 'wellCluster']] = (
        df_input[['wellName', 'workHorizon', 'nameDate', 'wellCluster']].astype('str'))
    df_input['nameDate'] = pd.to_datetime(df_input['nameDate'])
    df_input['oilfield'] = df_input['oilfield'].str.upper()

    # create a base coordinate for each well
    df_input.loc[df_input["coordinateXT3"] == 0, 'coordinateXT3'] = df_input.coordinateXT1
    df_input.loc[df_input["coordinateYT3"] == 0, 'coordinateYT3'] = df_input.coordinateYT1
    df_input.loc[df_input["coordinateXT1"] == 0, 'coordinateXT1'] = df_input.coordinateXT3
    df_input.loc[df_input["coordinateYT1"] == 0, 'coordinateYT1'] = df_input.coordinateYT3
    df_input["length of well T1-3"] = np.sqrt(np.power(df_input.coordinateXT3 - df_input.coordinateXT1, 2)
                                              + np.power(df_input.coordinateYT3 - df_input.coordinateYT1, 2))

    df_input["well type"] = 0
    df_input.loc[df_input["length of well T1-3"] < min_length_horWell, "well type"] = "vertical"
    df_input.loc[
        df_input["length of well T1-3"] >= min_length_horWell, "well type"] = "horizontal"

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

    return df_input


def upload_gdis_data(df_input, date, dict_parameters):
    """
    Загрузка данных по проведенным ГДИС на месторождении и удаление из входных данных
    скважин, на которых проводились исследования начиная с введенной пользователем даты по сей день

    :param df_input: DataFrame, полученный путем считывания исходного файла со скважинами
    :param date: дата выгрузки файла со скважинами
    :param dict_parameters: словарь с параметрами расчета
    :return: DataFrame очищенный от скважин, на которых проводились ГДИС не более n лет назад
    """
    application_path = get_path()
    logger.info("Upload GDIS file")
    df_gdis = pd.read_excel(os.path.join(application_path, dict_parameters['gdis_file']), skiprows=[0])

    # get preparing dataframes
    df_gdis = gdis_preparing(df_gdis, df_input['wellName'], date)

    # drop wells by horizon gdis
    objects = df_gdis.groupby(['wellName'])['workHorizon'].apply(lambda x: set(x.explode()))
    df_input = df_input.apply(lambda x: drop_wells_by_gdis(x, objects), axis=1)
    df_input = df_input[df_input['workHorizon'] != '']

    return df_input


def preparing(dict_constant, df_input, count_of_hor, watercut, fluid_rate, list_exception):
    """
    Подготовка к расчету DataFrame, прошедшего предварительную подготовку в зависимости от типа выгрузки

    :param fluid_rate: ограничение по дебиту жидкости
    :param dict_constant: словарь со статусами работы скважин
    :param watercut: ограничение на обводненность
    :param list_exception: список имен исключаемых скважин
    :param count_of_hor: кол-во объектов, заданное пользователем
    :param df_input: DataFrame, полученный из входного файла
    :return: Возврат DataFrame, подготовленного к расчету
    """

    PROD_STATUS, PROD_MARKER, PIEZ_STATUS, INJ_MARKER, INJ_STATUS, DELETE_MARKER = unpack_status(dict_constant)

    # rename columns
    # df_input.columns = dict_names.values()

    # cleaning null values
    df_input = df_input[df_input.workHorizon.notnull()]
    df_input = df_input[df_input.wellCluster.notnull()]
    df_input = df_input.fillna(0)

    # transfer to string type
    df_input[['wellName', 'workMarker', 'workHorizon', 'nameDate', 'wellCluster']] = df_input[
        ['wellName', 'workMarker', 'workHorizon', 'nameDate', 'wellCluster']].astype('str')

    df_input['nameDate'] = pd.to_datetime(df_input['nameDate'])

    # cleaning work horizon
    df_input = clean_work_horizon(df_input, count_of_hor)

    df_input = df_input[(df_input['workMarker'] != 0) & (df_input['wellStatus'] != 0)]

    # cleaning workMarker
    df_input = df_input.loc[~df_input.workMarker.map(str.lower).str.contains(DELETE_MARKER)]

    # cleaning wellStatus
    df_input = df_input[~(df_input.wellStatus.map(str.lower).str.contains(DELETE_MARKER))]

    # marker production wells (oil, gas, gas condensate)
    df_input['fond'] = 0
    df_input.loc[(df_input.workMarker.map(str.lower).str.contains(PROD_MARKER)) & (
        df_input.wellStatus.map(str.lower).str.contains(PROD_STATUS)), 'fond'] = 'ДОБ'
    # marker injection wells (water injection, gas injection)
    df_input.loc[(df_input.workMarker.map(str.lower).str.contains(INJ_MARKER)) & (
        df_input.wellStatus.map(str.lower).str.contains(INJ_STATUS)), 'fond'] = 'НАГ'
    # marker piezometric wells
    df_input.loc[df_input.wellStatus.map(str.lower).str.contains(PIEZ_STATUS), 'fond'] = 'ПЬЕЗ'
    df_input = df_input[df_input['fond'] != 0]

    # separation production gas, oil, gas condensate wells
    df_input['gasStatus'] = 0
    df_input['gasStatus'] = df_input['gasStatus'].where(
        (df_input['fond'] != 'ДОБ') | (df_input['gasRate'] == 0) | (df_input['condRate'] != 0), 'газовая')
    df_input['gasStatus'] = df_input['gasStatus'].where(
        (df_input['fond'] != 'ДОБ') | (df_input['condRate'] == 0), 'газоконденсатная')
    df_input['gasStatus'] = df_input['gasStatus'].where(
        (df_input['fond'] != 'ДОБ') | (df_input['gasRate'] != 0) | (df_input['condRate'] != 0), 'нефтяная')

    # separation injection wells to water injection and gas injection
    df_input['gasStatus'] = df_input['gasStatus'].where(
        (df_input['fond'] != 'НАГ') | (df_input['injectivity_day'] <= 2000), 'газонагнетательная')
    df_input['gasStatus'] = df_input['gasStatus'].where(
        (df_input['fond'] != 'НАГ') | (df_input['injectivity_day'] >= 2000), 'водонагнетательная')

    # separation piezometric wells
    df_input['gasStatus'] = df_input['gasStatus'].where(df_input['fond'] != 'ПЬЕЗ', 'пьезометрическая')

    # delete production wells with fluid rate less than fluid_rate in parameters
    df_input = df_input[~((df_input['fond'] == 'ДОБ') & (df_input.fluidRate <= fluid_rate))]
    # delete production wells with water cut less
    df_input = df_input[~((df_input['gasStatus'] == 'ДОБ') & (df_input.water_cut <= watercut))]

    # clean piez and inj wells from exception
    if list_exception:
        df_input['wellName'] = df_input.apply(
            lambda x: exception_marker(list_exception, x.wellName, x.fond), axis=1)
        df_input = df_input[df_input['wellName'] != '']

    df_input['oilfield'] = list(map(lambda x: str(x).upper(), df_input['oilfield']))
    df_input['water_cut'] = df_input.apply(lambda x: 100 if (x.water_cut == 0 and
                                                             str(x.fond) == 'НАГ') else x.water_cut, axis=1)

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

    date = pd.to_datetime(df_input['nameDate'].iloc[0], format='%d.%m.%Y')

    return df_input, date


def gdis_preparing(df_gdis, input_wells, year):
    """
    Функция очищает загруженные данные ГДИС от скважин, на которых
    ГДИС проводились раньше указанной пользователем даты

    :param df_gdis: данные ГДИС из файла с исследованиями по скважинам, считанные в DataFrame
    :param input_wells: имена всех скважин, входящих в исходный файл со скважинами
    :param year: опция расчета, задается в формате ДД/ММ/ГГГГ
    :return: возвращает DataFrame со скважинами, на которых ГДИС проводились более n(year) лет назад
    """
    logger.info("Preparing GDIS file")
    dict_names_gdis = {
        'Скважина': 'wellName',
        'Пласты': 'workHorizon',
        'Вид исследования': 'type_of_research',
        'Начальная дата': 'begin_of_research',
        'Дата окончания': 'end_of_research',
        'Оценка': 'quality'
    }

    # HIGH: str = "результат достоверный"
    # MEDIUM: str = "результат оценочный"
    LOW = ["результат ненадежен", "низкая"]
    # LOW: str = "низкая"

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
    df_gdis = df_gdis[~df_gdis['quality'].isin(LOW)]
    df_gdis['time_of_research'] = df_gdis['end_of_research'] - df_gdis['begin_of_research']
    df_gdis = df_gdis[df_gdis['time_of_research'] != timedelta(0)]
    df_gdis = df_gdis[df_gdis['end_of_research'] >= pd.to_datetime(year, format='%d.%m.%Y')]
    # df_gdis['how_long_ago'] = (pd.to_datetime(current_date, format='%d.%m.%Y') - df_gdis[
    #     'end_of_research']).dt.days / 365  # разница между датой
    # окончания ГДИС и датой выгрузки файла
    # df_gdis = df_gdis[(df_gdis['how_long_ago'] >= 0) & (df_gdis['how_long_ago'] <= year)]  # удаление ГДИС, которые
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


def preparing_reservoir_properties(dict_parameters, path):
    """
    Подготовка PVT свойств из справочника PVT и далее запись в .json файл
    для быстрого дотсупа к свойствам объектов в процессе расчета

    :param dict_parameters: словарь с параметрами расчета
    :param path: путь к корневой папке
    :return: сохраняет словарь в корневую папку в виде json файла со свойствами месторождений
    """
    application_path = get_path()
    df_property = pd.read_excel(os.path.join(application_path, dict_parameters['property_file']), skiprows=[0])
    dict_names_prop = {
        'Месторождение': 'oilfield',
        'Пласт OIS': 'reservoir',
        'Рпл.нач., кгс/см2 =Мпа*10.2             (проект. документ)': 'pressure',
        'μн. в пл. усл., сП': 'oil_visc',
        'μв. в пл. усл., сП': 'water_visc',
        'm,     %': 'porosity',
        'β, 1/атм*10-5 породы': 'rock_compr',
        'β, 1/атм*10-5 нефть': 'oil_compr',
        'β, 1/атм*10-5 вода': 'water_copmr',
        'μг., сП в пласт. усл.': 'gas_visc',
        'Степень Krw  (для ОФП)': 'Krw_degree',
        'Степень для функции Krw (доп)  (для ОФП)': 'Krw_func',
        'Степень Kro  (для ОФП)': 'Kro_degree',
        'Степень для функции Kro (доп)  (для ОФП)': 'Kro_func',
        'Swo (для ОФП)': 'Swo',
        'Swk  (для ОФП)': 'Swk',
        'Krwk  (для ОФП)': 'K_wmax',
        'Krok  (для ОФП)': 'K_omax',
        'Кпрон (средняя) по нефти': 'K_abs'
    }
    df_property.columns = df_property.columns.str.strip()
    df_property = df_property[['Месторождение', 'Пласт OIS', 'Рпл.нач., кгс/см2          (карты изобар)',
                               'μн. в пл. усл., сП', 'μв. в пл. усл., сП',
                               'm,     %', 'β, 1/атм*10-5 породы', 'β, 1/атм*10-5 нефть',
                               'β, 1/атм*10-5 вода', 'μг., сП в пласт. усл.', 'Степень Krw  (для ОФП)',
                               'Степень для функции Krw (доп)  (для ОФП)', 'Степень Kro  (для ОФП)',
                               'Степень для функции Kro (доп) (для ОФП)', 'Swo (для ОФП)', 'Swk  (для ОФП)',
                               'Krwk  (для ОФП)', 'Krok  (для ОФП)', 'Кпрон (средняя) по нефти']]
    df_property.columns = dict_names_prop.values()
    for i in df_property.columns:
        df_property[i] = list(map(lambda x: str(x).strip(), df_property[i]))
        if i != 'oilfield' and i != 'reservoir':
            df_property[i] = list(map(lambda x: float(str(x).replace(',', '.')), df_property[i]))
    df_property = df_property.groupby(by=['oilfield', 'reservoir'], as_index=False).mean()
    df_property['horizon'] = list(map(lambda x, y: f'{x}__{y}', df_property.oilfield, df_property.reservoir))
    df_property['Sno'] = list(map(lambda x: round(1 - x, 3), df_property['Swk']))
    df_property[['oilfield', 'reservoir']] = df_property[['oilfield', 'reservoir']].astype('str')
    # df_property.index.set_names(df_property['horizon'])
    # df_property = df_property.reset_index(drop=True)
    df_property = df_property.fillna(0)
    list_oilfield_res = list(df_property['horizon'].explode().unique())
    list_properties = ['porosity', 'pressure', 'oil_compr', 'water_copmr', 'rock_compr', 'oil_visc',
                       'water_visc', 'gas_visc', 'K_wmax', 'K_omax', 'Swo', 'Swk', 'Sno',
                       'Krw_degree', 'Krw_func', 'Kro_degree', 'Kro_func', 'K_abs']
    list_oilfield = list(df_property['oilfield'].explode().unique())

    dict_properties = dict.fromkeys(list_properties)
    # запись свойств в словарь по данным из файла в виде месторождение/объект/свойства
    dict_PVT = {}
    for oil_res in list_oilfield_res:
        oilfield = str(oil_res).split('__')[0]
        if oilfield not in dict_PVT:
            dict_PVT[oilfield] = {}
        res = str(oil_res).split('__')[1]
        dict_PVT[oilfield][res] = {}
        for prop in list_properties:
            dict_PVT[oilfield][res][prop] = df_property[
                (df_property['oilfield'] == oilfield) & (df_property['reservoir'] == res)][prop].values[0]

    #  подсчет средних свойств по объектам для каждого месторождения
    for oilfield in list_oilfield:
        dict_mean_prop = dict.fromkeys(list_properties)
        for prop in list_properties:
            dict_mean_prop[prop] = df_property[df_property['oilfield'] == oilfield][prop].mean()
        dict_PVT[oilfield]['DEFAULT_OBJ'] = dict_mean_prop

    with open(path, 'w', encoding='UTF-8') as file:
        json_string = json.dumps(dict_PVT, default=lambda o: o.__dict__, ensure_ascii=False, sort_keys=True,
                                 indent=2)
        file.write(json_string)

    pass


def get_exception_wells(dict_parameters):
    """
    Загрузка скважин для исключения из расчета

    :param dict_parameters: словарь с параметрами расчета
    :return: возвращает список скважин для исключения
    """
    application_path = get_path()
    df_exception = pd.read_excel(os.path.join(application_path, dict_parameters['exception_file']), header=None)
    df_exception[0] = df_exception[0].astype(str)
    list_exception = list(df_exception[0].explode().unique())

    return list_exception
