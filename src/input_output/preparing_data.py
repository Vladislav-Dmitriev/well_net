import json
import os
import sys
from tqdm import tqdm
from datetime import timedelta
import numpy as np
import pandas as pd
import xlwings as xw
from dateutil.parser import parse as parseDate
from loguru import logger
from shapely.geometry import Point, LineString
from src.calculation.support_functions import get_path, clean_work_horizon, unpack_status, min_color_diff
from src.calculation.shapely_geometry import check_intersection_area
from .dictionaries import dict_geobd_columns, dict_ngt_column, dict_project_columns, dict_ngt_encoding


@logger.catch
def upload_input_data(dict_constant, dict_parameters, log_user, progress_bar):
    """
    Считывание файла с исключенными скважинами, затем загрузка данных,
    их подготовка к расчету в зависимости от базы данных
    и удаление исключенных скважин, загрузка проектных скважин при наличии

    :param dict_constant: словарь со статусами работы скважин
    :param dict_parameters: словарь с параметрами расчета
    :param log_user: сигнал для передачи сообщения пользователю в окно логирования
    :param progress_bar: сигнал передачи значения в линию прогресса текущей задачи

    :return: возвращает подготовленный DataFrame после считывания исходного файла со скважинами
    """

    # Upload project wells
    df_project = preparing_project_wells(dict_parameters, log_user, progress_bar)

    # Upload exception list wells
    log_user.emit("Считывание листа исключенных скважин")
    progress_bar.emit(0)
    df_excluded_wells = get_exception_wells(dict_parameters, 'Исключения', log_user)
    progress_bar.emit(100)

    # Get path to application folder
    application_path = get_path()
    logger.info("Data type definition")
    log_user.emit("Определение типа выгрузки")
    progress_bar.emit(0)
    # read first row of file
    first_row = pd.read_excel(os.path.join(application_path, "input", dict_parameters['data_file']), header=None,
                              sheet_name='Фонд', nrows=1)
    progress_bar.emit(100)
    # check type of database by values of first row
    if first_row.loc[0][0] == '№ скважины':
        logger.info("Preparing NGT data")
        log_user.emit("Тип выгрузки NGT")
        log_user.emit("Чтение данных по скважинам")
        progress_bar.emit(0)
        df = pd.read_excel(os.path.join(application_path, "input", dict_parameters['data_file']), header=0,
                           skiprows=[1],
                           sheet_name='Фонд')
        progress_bar.emit(100)
        df = df.dropna(subset=['№ скважины'])
        # preprocessing NGT data
        log_user.emit("Подготовка выгрузки из NGT")
        df_input, df_exceptions = preprocessing_NGT(df, dict_parameters['min_length_horWell'], progress_bar)
        logger.info("General preparing data")
        log_user.emit("Подготовка данных к расчету")
        df_input, df_exceptions = preparing(dict_constant, df_input, df_exceptions, dict_parameters, progress_bar)
        # add project wells to input DataFrame
        df_input = pd.concat([df_input, df_project], axis=0, sort=False).reset_index(drop=True)
        df_input = df_input.fillna(0)
        df_input['num_of_research'] = False
        # gdis data accounting
        logger.info("GDIS data accounting")
        log_user.emit("Учет данных о проведенных исследованиях NGT")
        df_input, df_exceptions = ngt_gdis_data(df_input, df_exceptions, dict_parameters, log_user, progress_bar)
    # check type of database by values of first row
    elif first_row.loc[0][0] == 'NSKV':
        logger.info("Preparing GeoBD data")
        log_user.emit("Тип выгрузки ГеоБД")
        log_user.emit("Чтение данных по скважинам")
        progress_bar.emit(0)
        df = pd.read_excel(os.path.join(application_path, "input", dict_parameters['data_file']), header=0,
                           skiprows=[1],
                           sheet_name='Фонд')
        progress_bar.emit(100)
        df = df.dropna(subset=['NSKV'])
        log_user.emit("Подготовка выгрузки из ГеоБД")
        df_input, df_exceptions = preprocessing_GeoBD(df, dict_constant, dict_geobd_columns, progress_bar)
        logger.info("General preparing data")
        log_user.emit("Подготовка данных к расчету")
        df_input, df_exceptions = preparing(dict_constant, df_input, df_exceptions, dict_parameters, progress_bar)
        # add project wells to input DataFrame
        df_input = pd.concat([df_input, df_project], axis=0, sort=False).reset_index(drop=True)
        df_input = df_input.fillna(0)
        df_input['num_of_research'] = False
        # gdis data accounting
        log_user.emit("Учет данных о проведенных исследованиях ГеоБД")
        df_input, df_exceptions = geobd_gdis_data(df_input, df_exceptions, dict_parameters, log_user, progress_bar)
    # if wrong type of database
    else:
        logger.info('Wrong data format')
        log_user.emit("Неверный формат файла загрузки")
        sys.exit()
    # Upload necessarily research wells
    list_necessarily = get_necessarily_wells(dict_parameters, 'Приоритетные скважины', log_user)
    df_input.loc[df_input['wellName'].str.split("_").str[0].isin(list_necessarily), 'num_of_research'] = True
    return df_input, df_exceptions, df_excluded_wells


@logger.catch(level='DEBUG')
def preprocessing_GeoBD(df_input, dict_constant, dict_geobd_columns, progress_bar):
    """
    Подготовка данных ГеоБД

    :param df_input: Выгрузка данных ГеоБД
    :param dict_constant: статусы и характеры работы скважин
    :param dict_geobd_columns: список имен столбцов
    :param progress_bar: сигнал передачи значения в линию прогресса текущей задачи
    :return: DataFrame с необходимыми столбцами для расчета, столбцы в правильном порядке,
    скважины разделены на ННС и ГС
    """

    progress_bar.emit(0)
    PROD_STATUS, PROD_MARKER, PIEZ_STATUS, INJ_MARKER, INJ_STATUS, DELETE_MARKER = unpack_status(dict_constant)
    # fill NaN cells
    df_input = df_input.fillna(0)
    # create DataFrame of exception wells, also add wellnet status to them
    df_exceptions = df_input[(df_input['KUST'] == 0) | (df_input['SOST'] == 0) | (df_input['PLAST'] == 0)]
    df_exceptions['wellNet'] = 'Исключена из расчета, куст/пласт/состояние'
    # delete from input DataFrame wells with no information about cluster, status, reservoir
    df_input = df_input[(df_input['KUST'] != 0) & (df_input['SOST'] != 0) & (df_input['PLAST'] != 0)]
    df_input[['NSKV', 'SIMVOL', 'PLAST', 'STATUS_DATE', 'PEREV']] = (
        df_input[['NSKV', 'SIMVOL', 'PLAST', 'STATUS_DATE', 'PEREV']].astype('str'))
    df_exceptions[['NSKV', 'SIMVOL', 'PLAST', 'STATUS_DATE', 'PEREV']] = \
        (df_exceptions[['NSKV', 'SIMVOL', 'PLAST', 'STATUS_DATE', 'PEREV']].astype('str'))
    # cleaning wellStatus
    df_exceptions = pd.concat([df_exceptions, df_input.loc[df_input.SOST.map(str.lower).str.contains(DELETE_MARKER)]],
                              axis=0, sort=False).reset_index(drop=True)
    df_exceptions.loc[df_exceptions['wellNet'].isnull(), 'wellNet'] = 'Исключена из расчета по состоянию'
    df_input = df_input.loc[~df_input.SOST.map(str.lower).str.contains(DELETE_MARKER)]
    # check well status of tranfer on another oil reservoir
    df_exceptions = pd.concat([df_exceptions,
                               df_input[(df_input['PEREV'] != 'совмест.') & (df_input['PEREV'] != 'работает')]],
                              axis=0, sort=False).reset_index(drop=True)
    df_exceptions.loc[df_exceptions['wellNet'].isnull(), 'wellNet'] = 'Исключена из расчета, переведена/не работает'
    df_input = df_input[(df_input['PEREV'] == 'совмест.') | (df_input['PEREV'] == 'работает')]
    #  reset indexes in DataFrames
    df_input = df_input.reset_index(drop=True)

    # create list of required columns
    required_cols = ['NSKV', 'UWI', 'STATUS_DATE', 'FOND', 'SOST', 'MEST',
                     'PLAST', 'PEREV', 'KUST', 'SIMVOL', 'X', 'X3', 'Y', 'Y3',
                     'DEBOIL', 'DEBLIQ', 'PRIEM', 'VPROCOBV', 'SPOSOB', 'DEBGAS', 'PRIEMGAS', 'DEBCOND']
    progress_bar.emit(25)
    # add columns with oilfield name and coordinates T3 point
    df_input = add_t3_coord_geobd(df_input, required_cols)
    progress_bar.emit(50)
    # add columns with oilfield name and coordinates T3 point
    df_exceptions = add_t3_coord_geobd(df_exceptions, required_cols + ['wellNet'])
    progress_bar.emit(75)

    df_input.drop(columns=['UWI', 'PEREV'], axis=1, inplace=True)
    df_exceptions.drop(columns=['UWI', 'PEREV'], axis=1, inplace=True)
    correct_order = ['NSKV', 'STATUS_DATE', 'FOND', 'SOST', 'MEST', 'PLAST', 'KUST', 'SIMVOL', 'X', 'X3',
                     'Y', 'Y3', 'DEBOIL', 'DEBLIQ', 'DEBGAS', 'PRIEM', 'PRIEMGAS', 'VPROCOBV', 'SPOSOB', 'DEBCOND',
                     'well type']

    df_input = df_input[correct_order]
    df_exceptions = df_exceptions[correct_order + ['wellNet']]
    df_input.columns = dict_geobd_columns.values()
    df_exceptions.columns = {**dict_geobd_columns, **{'wellNet': 'wellNet'}}.values()
    # нужно перевести столбец приемистости по газу 'injectivity_day' в м3/сут как в NGT, а в ГеоБД этот столбец в тыс. м3/сут
    df_input['injectivity_day'] = df_input['injectivity_day'] * 1000
    progress_bar.emit(100)

    return df_input, df_exceptions


@logger.catch(level='DEBUG')
def add_t3_coord_geobd(df, list_columns):
    """
    Подготовка DataFrame к расчету, удаление дубликатов с "_Т3" и добавление координат Т3 первого ствола для ГС
    :param df: DataFrame для подготовки к расчету, удаление дубликатов в столбце имен и добавление столбцов с T3
    :param list_columns: список столбцов, которые необходимо оставить для дальнейшего расчета
    :return: DataFrame скважин с подготовленными координатами
    """
    df['MEST'] = list(str(df.loc[0]['LINK']).split('='))[-1].upper()
    df['X3'] = 0
    df['Y3'] = 0
    df = df[list_columns]
    list_well_names = list(df['UWI'].explode().unique())  # list of unique well names
    df = df.sort_values(by=['NSKV'], ascending=True).reset_index(drop=True)
    df[["NSKV"]] = df[["NSKV"]].astype(str)
    df['well type'] = ''
    # iterate by well names
    for well in list_well_names:
        objs = list(
            df[df['UWI'] == well].PLAST.explode().unique())  # list of unique work objects current well
        if len(objs) > 1:
            for ob in objs:
                df.loc[(df['UWI'] == well) & (df["PLAST"] == ob), 'VPROCOBV'] = \
                    list(df.loc[df['UWI'] == well, 'VPROCOBV'].explode())[0]
                # T1 coordinates for horizontal well are taken from first wellbore, T3 from last wellbore
                coord_x = list(df[(df['UWI'] == well) & (df["PLAST"] == ob)].X.explode().unique())
                coord_y = list(df[(df['UWI'] == well) & (df["PLAST"] == ob)].Y.explode().unique())
                df.loc[(df['UWI'] == well) & (df["PLAST"] == ob), 'X'] = coord_x[0]
                df.loc[(df['UWI'] == well) & (df["PLAST"] == ob), 'X3'] = coord_x[-1]
                df.loc[(df['UWI'] == well) & (df["PLAST"] == ob), 'Y'] = coord_y[0]
                df.loc[(df['UWI'] == well) & (df["PLAST"] == ob), 'Y3'] = coord_y[-1]
                # if mask dataframe by uniq UWI and object get more than 1 rows well type will be horizontalKa
                if df[(df["UWI"] == well) & (df["PLAST"] == ob)].shape[0] > 1:
                    # name but they have same geobd encoding then well is horizontal
                    df.loc[(df["UWI"] == well) & (df["PLAST"] == ob), "well type"] = "horizontal"
                else:
                    # in other variants wells will be determined as vertical
                    df.loc[(df["UWI"] == well) & (df["PLAST"] == ob), 'well type'] = 'vertical'

                df.loc[(df["UWI"] == well) & (df["PLAST"] == ob), "UWI"] = df.loc[(df["UWI"] == well) & (
                            df["PLAST"] == ob), "UWI"] + f"_БС{objs.index(ob) + 1}"
                df.loc[(df["UWI"] == well + f"_БС{objs.index(ob) + 1}") & (df["PLAST"] == ob), "NSKV"] = df.loc[
                    (df["UWI"] == well + f"_БС{objs.index(ob) + 1}") & (df["PLAST"] == ob), "NSKV"].copy().apply(
                    lambda x: x + f"_БС{objs.index(ob) + 1}")

        else:
            # if mask dataframe by uniq UWI and object get more than 1 rows well type will be horizontalKa
            if df[df["UWI"] == well].shape[0] > 1:
                # name but they have same geobd encoding then well is horizontal
                df.loc[df["UWI"] == well, "well type"] = "horizontal"
            else:
                # in other variants wells will be determined as vertical
                df.loc[df["UWI"] == well, 'well type'] = 'vertical'
            # value of watercut is taken from the first wellbore
            df.loc[df['UWI'] == well, 'VPROCOBV'] = \
                list(df.loc[df['UWI'] == well, 'VPROCOBV'].explode())[0]
            # T1 and T3 coordinates for vertical well are taken from first wellbore
            coord_x = list(df[df['UWI'] == well].X.explode().unique())
            coord_y = list(df[df['UWI'] == well].Y.explode().unique())
            df.loc[df['UWI'] == well, 'X'] = coord_x[0]
            df.loc[df['UWI'] == well, 'X3'] = coord_x[0]
            df.loc[df['UWI'] == well, 'Y'] = coord_y[0]
            df.loc[df['UWI'] == well, 'Y3'] = coord_y[0]
        # writing wells object to columns PLAST separated by commas
        df.loc[df['UWI'] == well, 'PLAST'] = df[df['UWI'] == well].apply(lambda x: ', '.join(objs), axis=1)
    # leave only unique wells by geobd encoding column
    df = df.drop_duplicates(subset=['UWI'], keep="first")
    # find duplicates in NSKV column
    duplicates_mask = df["NSKV"].duplicated(keep=False)
    # add numbering only for duplicates
    if duplicates_mask.sum() > 0:  # check num of duplicates
        df.loc[duplicates_mask, "NSKV"] = (
            df[duplicates_mask].groupby("NSKV").cumcount().add(1).astype(str).radd(
                df.loc[duplicates_mask, "NSKV"] + "_")
        )
    return df


@logger.catch(level='DEBUG')
def preparing_project_wells(dict_parameters, log_user, progress_bar):
    """
    Чтение файла с проектными скважинами, обработка координат и разделение на типы ННС/ГС

    :param dict_parameters: словарь с параметрами расчета
    :param progress_bar: сигнал передачи значения в линию прогресса текущей задачи
    :param log_user: сигнал для передачи сообщения пользователю в окно логирования
    :return: подготовленный DataFrame с проектными скважинами
    """
    logger.info('Preparing project wells')
    # get application path to read required file
    application_path = get_path()
    try:
        log_user.emit("Чтение листа с проектными скважинами")
        progress_bar.emit(0)
        df_project = pd.read_excel(os.path.join(application_path, "input", dict_parameters['data_file']),
                                   header=0, skiprows=[1], decimal='.', sheet_name='Проектный фонд')
        if df_project.empty:
            log_user.emit("Проектных скважин не найдено")
            progress_bar.emit(100)
            return pd.DataFrame()
    except ValueError:
        log_user.emit("Лист с данными по проектному фонду не найден")
        logger.info('Sheet with name "Проектный фонд" not found in data file')
        progress_bar.emit(100)
        return pd.DataFrame()
    progress_bar.emit(100)
    # delete spaces in cells with well names and objects
    df_project['NSKV'] = df_project['NSKV'].apply(lambda x: str(x).strip())
    df_project['PLAST'] = df_project['PLAST'].apply(lambda x: str(x).strip())
    # assign values from NSKV to UWI column with delete '_T3'
    df_project['UWI'] = df_project['NSKV'].str.replace('_T3', '')

    df_project['X3'] = 0
    df_project['Y3'] = 0

    list_well_names = list(df_project['UWI'].explode().unique())  # list unique names of wells
    total_wells_count = len(list_well_names)
    df_project = df_project.sort_values(by=['NSKV'], ascending=True)
    df_project.reset_index(drop=True)
    df_project['well type'] = ''
    log_user.emit("Подготовка координат проектных скважин")
    progress_bar.emit(0)  # update progress bar value

    for well in tqdm(list_well_names, "Preparing project wells", position=0, leave=True,
                     colour='white', ncols=80, disable=True):
        objs = list(
            df_project[df_project['UWI'] == well].PLAST.explode().unique())  # list of unique well objects

        if len(set(df_project[df_project['UWI'] == well].NSKV)) > 1:  # if in column of well names there are more than 1
            # name but they have same geobd encoding then well is horizontal
            df_project.loc[df_project['UWI'] == well, 'well type'] = 'horizontal'

        else:
            df_project.loc[df_project['UWI'] == well, 'well type'] = 'vertical'

        coord_x = list(df_project[df_project['UWI'] == well].X.explode().unique())
        coord_y = list(df_project[df_project['UWI'] == well].Y.explode().unique())
        df_project.loc[df_project['UWI'] == well, 'X'] = coord_x[0]
        df_project.loc[df_project['UWI'] == well, 'X3'] = coord_x[-1]
        df_project.loc[df_project['UWI'] == well, 'Y'] = coord_y[0]
        df_project.loc[df_project['UWI'] == well, 'Y3'] = coord_y[-1]
        # writing wells object to columns PLAST separated by commas
        df_project.loc[df_project['UWI'] == well, 'PLAST'] = df_project.apply(lambda x: ', '.join(objs), axis=1)
        # update progress bar of cycle
        progress_bar.emit(int((list_well_names.index(well) + 1) / total_wells_count * 100))

    df_project = df_project.drop_duplicates(subset=['UWI'])
    df_project.drop(columns=['UWI'], axis=1, inplace=True)
    df_project = df_project[['NSKV', 'X', 'X3', 'Y', 'Y3', 'PLAST', 'well type']]
    df_project.columns = dict_project_columns.values()

    # add well number markers
    df_project["marker_num"] = "33"

    # add to input dataframe columns for shapely types of coordinates
    df_project.insert(loc=df_project.shape[1], column="POINT",
                      value=list(map(lambda x, y: Point(x, y), df_project.coordinateX, df_project.coordinateY)))

    df_project.insert(loc=df_project.shape[1], column="POINT3",
                      value=list(map(lambda x, y: Point(x, y), df_project.coordinateX3, df_project.coordinateY3)))
    df_project.insert(loc=df_project.shape[1], column="GEOMETRY", value=0)
    df_project["GEOMETRY"] = df_project["GEOMETRY"].where(df_project["well type"] != "vertical",
                                                          list(map(lambda x: x, df_project.POINT)))
    df_project["GEOMETRY"] = df_project["GEOMETRY"].where(df_project["well type"] != "horizontal",
                                                          list(map(lambda x, y: LineString(
                                                              tuple(x.coords) + tuple(y.coords)),
                                                                   df_project.POINT, df_project.POINT3)))

    df_project['fond'] = 'ПРОЕКТ'

    return df_project


@logger.catch(level='DEBUG')
def preparing(dict_constant, df_input, df_exceptions, dict_parameters, progress_bar):
    """
    Подготовка к расчету DataFrame, прошедшего предварительную подготовку в зависимости от типа выгрузки

    :param dict_constant: словарь со статусами работы скважин
    :param df_input: DataFrame, полученный из входного файла
    :param df_exceptions: DataFrame исключенных скважин в ходе подготовки к расчету
    :param dict_parameters: словарь с параметрами расчета
    :param progress_bar: сигнал передачи значения в линию прогресса текущей задачи
    :return: Возврат DataFrame, подготовленного к расчету
    """

    progress_bar.emit(0)
    PROD_STATUS, PROD_MARKER, PIEZ_STATUS, INJ_MARKER, INJ_STATUS, DELETE_MARKER = unpack_status(dict_constant)

    # transfer columns to string type
    logger.info("Transfer columns to string type")
    df_input[['wellName', 'workMarker', 'workHorizon', 'nameDate', 'wellCluster']] = df_input[
        ['wellName', 'workMarker', 'workHorizon', 'nameDate', 'wellCluster']].astype('str')
    df_exceptions[['wellName', 'wellStatus', 'workMarker', 'workHorizon', 'nameDate', 'wellCluster']] = df_exceptions[
        ['wellName', 'wellStatus', 'workMarker', 'workHorizon', 'nameDate', 'wellCluster']].astype('str')
    logger.info("Column date to datetime format")
    df_input['nameDate'] = pd.to_datetime(df_input['nameDate'])
    # cleaning work horizon
    logger.info("Cleaning work horizon")
    df_input, df_exception_by_hor = clean_work_horizon(df_input, dict_parameters['horizon_count'])
    df_exceptions = pd.concat([df_exceptions, df_exception_by_hor], axis=0, sort=False).reset_index(drop=True)
    df_exceptions.loc[df_exceptions['wellNet'].isnull(), 'wellNet'] = 'Исключена по кол-ву пластов'
    progress_bar.emit(25)

    # cleaning wellStatus
    logger.info("Status division")
    df_exceptions = pd.concat([df_exceptions, df_input[df_input.wellStatus.map(str.lower).str.contains(DELETE_MARKER)]],
                              axis=0, sort=False).reset_index(drop=True)
    df_exceptions.loc[df_exceptions['wellNet'].isnull(), 'wellNet'] = 'Исключена из расчета по состоянию'
    df_input = df_input[~(df_input.wellStatus.map(str.lower).str.contains(DELETE_MARKER))]

    logger.info("Marker production wells (oil, gas, gas condensate)")
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
    progress_bar.emit(50)

    # separation production gas, oil, gas condensate wells
    logger.info("Separation production gas, oil, gas condensate wells")
    df_input['gasStatus'] = 0
    df_input['gasStatus'] = df_input['gasStatus'].where(
        (df_input['fond'] != 'ДОБ') | (df_input['gasRate'] == 0) | (df_input['condRate'] != 0), 'газовая')
    df_input['gasStatus'] = df_input['gasStatus'].where(
        (df_input['fond'] != 'ДОБ') | (df_input['condRate'] == 0), 'газоконденсатная')
    df_input['gasStatus'] = df_input['gasStatus'].where(
        (df_input['fond'] != 'ДОБ') | (df_input['gasRate'] != 0) | (df_input['condRate'] != 0), 'нефтяная')

    # separation injection wells to water injection and gas injection
    logger.info("Separation injection wells to water injection and gas injection")
    df_input['gasStatus'] = df_input['gasStatus'].where(
        (df_input['fond'] != 'НАГ') | (df_input['injectivity_day'] <= 2000), 'газонагнетательная')
    df_input['gasStatus'] = df_input['gasStatus'].where(
        (df_input['fond'] != 'НАГ') | (df_input['injectivity_day'] >= 2000), 'водонагнетательная')

    # separation piezometric wells
    logger.info("Separation piezometric wells")
    df_input['gasStatus'] = df_input['gasStatus'].where(df_input['fond'] != 'ПЬЕЗ', 'пьезометрическая')
    df_input['gasStatus'] = df_input['gasStatus'].where(
        ~((df_input['fond'] == 'ПЬЕЗ') & (df_input['workMarker'].str.lower().str.contains('газ'))),
        'пьезометрическая газовая')
    progress_bar.emit(75)

    # delete production wells with oil rate bigger than value in parameters
    if dict_parameters['limit_oilrate'] != '':
        df_exceptions = pd.concat([df_exceptions, df_input[(df_input['gasStatus'] == 'нефтяная')
                                                           & (df_input['oilRate'] > dict_parameters['limit_oilrate'])]],
                                  axis=0, sort=False).reset_index(drop=True)
        df_exceptions.loc[df_exceptions['wellNet'].isnull(), 'wellNet'] = 'Исключена по дебиту нефти'
        df_input = df_input[
            ~((df_input['gasStatus'] == 'нефтяная') & (df_input['oilRate'] > dict_parameters['limit_oilrate']))]

    # delete production wells with fluid rate less than fluid_rate in parameters
    if dict_parameters['fluid_rate'] != '':
        df_exceptions = pd.concat([df_exceptions, df_input[(df_input['fond'] == 'ДОБ')
                                                           & (df_input['gasStatus'] == 'нефтяная')
                                                           & (df_input.fluidRate <= dict_parameters['fluid_rate'])]],
                                  axis=0, sort=False).reset_index(drop=True)
        df_exceptions.loc[df_exceptions['wellNet'].isnull(), 'wellNet'] = 'Исключена по дебиту жидкости'
        df_input = df_input[
            ~((df_input['fond'] == 'ДОБ') & (df_input['gasStatus'] == 'нефтяная') & (
                    df_input.fluidRate <= dict_parameters['fluid_rate']))]
    # delete production wells with water cut less
    if dict_parameters['water_cut'] != '':
        df_exceptions = pd.concat([df_exceptions, df_input[(df_input['fond'] == 'ДОБ')
                                                           & (df_input['gasStatus'] == 'нефтяная')
                                                           & (df_input.water_cut <= dict_parameters['water_cut'])]],
                                  axis=0, sort=False).reset_index(drop=True)
        df_exceptions.loc[df_exceptions['wellNet'].isnull(), 'wellNet'] = 'Исключена по обводненности'
        df_input = df_input[
            ~((df_input['fond'] == 'ДОБ') & (df_input['gasStatus'] == 'нефтяная') & (
                    df_input.water_cut <= dict_parameters['water_cut']))]

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
    df_input["GEOMETRY"] = df_input.apply(lambda x: x["POINT"] if x["GEOMETRY"].length == 0 else x["GEOMETRY"], axis=1)

    # add to exceptions dataframe columns for shapely types of coordinates
    df_exceptions["POINT"] = df_exceptions.apply(lambda x: Point(x['coordinateX'], x['coordinateY']), axis=1)
    df_exceptions["POINT3"] = df_exceptions.apply(lambda x: Point(x['coordinateX3'], x['coordinateY3']), axis=1)
    df_exceptions.insert(loc=df_exceptions.shape[1], column="GEOMETRY", value=0)
    df_exceptions["GEOMETRY"] = df_exceptions["GEOMETRY"].where(df_exceptions["well type"] != "vertical",
                                                                list(map(lambda x: x, df_exceptions.POINT)))
    df_exceptions["GEOMETRY"] = df_exceptions["GEOMETRY"].where(df_exceptions["well type"] != "horizontal",
                                                                list(map(lambda x, y: LineString(
                                                                    tuple(x.coords) + tuple(y.coords)),
                                                                         df_exceptions.POINT, df_exceptions.POINT3)))
    df_exceptions["GEOMETRY"] = df_exceptions.apply(
        lambda x: x["POINT"] if x["GEOMETRY"].length == 0 else x["GEOMETRY"], axis=1)
    progress_bar.emit(100)

    return df_input, df_exceptions


@logger.catch(level='DEBUG')
def preprocessing_NGT(df_input, min_length_horWell, progress_bar):
    """
    Подготовка данных из NGT

    :param df_input: Выгрузка данных NGT
    :param min_length_horWell: минимальная длина ГС, для разделения скважин на ННС и ГС
    :param progress_bar: сигнал передачи значения в линию прогресса текущей задачи
    :return: подготовленный DataFrame выгрузки NGT, скважины разделены на ННС и ГС
    """

    progress_bar.emit(0)
    # rename columns
    df_input.columns = dict_ngt_column.values()
    df_input = df_input.fillna(0)  # fill NaN cells
    progress_bar.emit(25)
    # add encoding for well signs
    df_input["marker_num"] = 34
    df_input["exploitation"] = df_input["exploitation"].astype(str)
    for _, row in df_input.iterrows():
        work = str(row["workMarker"]).lower()
        status = str(row["wellStatus"]).lower()
        exploitation = row["exploitation"].lower()
        try:
            if (work == "неф") or (work == "переведена на другой объект"):
                df_input.loc[df_input["wellName"] == row["wellName"], "marker_num"] = str(dict_ngt_encoding[work][status][exploitation])
            else:
                df_input.loc[df_input["wellName"] == row["wellName"], "marker_num"] = str(dict_ngt_encoding[work][status])
        except KeyError:
            pass
    # create exceptions DataFrame
    df_exceptions = df_input[
        (df_input['workHorizon'] == 0) | (df_input['wellCluster'] == 0) | (df_input['wellStatus'] == 0)]
    df_exceptions['wellNet'] = 'Исключена из расчета, куст/пласт/состояние'
    # cleaning null values
    df_input = df_input[(df_input['workHorizon'] != 0) & (df_input['wellCluster'] != 0) & (df_input['wellStatus'] != 0)]
    # transfer to string type columns of calculation DataFrame
    df_input[['wellName', 'workHorizon', 'nameDate', 'wellCluster']] = (
        df_input[['wellName', 'workHorizon', 'nameDate', 'wellCluster']].astype('str'))
    df_exceptions[['wellName', 'workHorizon', 'nameDate', 'wellCluster']] = (
        df_exceptions[['wellName', 'workHorizon', 'nameDate', 'wellCluster']].astype('str'))
    df_input['nameDate'] = pd.to_datetime(df_input['nameDate'])  # column of str time to timestamp
    df_input['oilfield'] = df_input['oilfield'].str.upper()  # uppercase of oilfield name in column
    progress_bar.emit(50)
    # create T1 and T3 coordinates for each well in nDataFrame
    df_input = add_t3_coord_ngt(df_input, min_length_horWell)
    progress_bar.emit(75)
    df_exceptions = add_t3_coord_ngt(df_exceptions, min_length_horWell)
    progress_bar.emit(100)

    return df_input, df_exceptions


@logger.catch(level='DEBUG')
def add_t3_coord_ngt(df, min_length_horWell):
    """
    Добавление координат T3 для всех скважин для возможности создания геометрии

    :param df: DataFrame с данными по скважинам из NGT
    :param min_length_horWell: минимальная заданная длина ГС
    :return: DataFrame с подготовленными координатами T1 и T3
    """
    # create a base coordinate for each well
    df.loc[df["coordinateXT3"] == 0, 'coordinateXT3'] = df.coordinateXT1
    df.loc[df["coordinateYT3"] == 0, 'coordinateYT3'] = df.coordinateYT1
    df.loc[df["coordinateXT1"] == 0, 'coordinateXT1'] = df.coordinateXT3
    df.loc[df["coordinateYT1"] == 0, 'coordinateYT1'] = df.coordinateYT3
    df["length of well T1-3"] = np.sqrt(np.power(df.coordinateXT3 - df.coordinateXT1, 2)
                                        + np.power(df.coordinateYT3 - df.coordinateYT1, 2))

    df["well type"] = 0
    df.loc[df["length of well T1-3"] < min_length_horWell, "well type"] = "vertical"
    df.loc[
        df["length of well T1-3"] >= min_length_horWell, "well type"] = "horizontal"

    df["coordinateX"] = 0
    df["coordinateX3"] = 0
    df["coordinateY"] = 0
    df["coordinateY3"] = 0
    df.loc[df["well type"] == "vertical", ['coordinateX', 'coordinateX3']] = df.coordinateXT1
    df.loc[df["well type"] == "vertical", ['coordinateY', 'coordinateY3']] = df.coordinateYT1
    df.loc[df["well type"] == "horizontal", 'coordinateX'] = df.coordinateXT1
    df.loc[df["well type"] == "horizontal", 'coordinateX3'] = df.coordinateXT3
    df.loc[df["well type"] == "horizontal", 'coordinateY'] = df.coordinateYT1
    df.loc[df["well type"] == "horizontal", 'coordinateY3'] = df.coordinateYT3

    # drop useless columns from DataFrame
    df.drop(["length of well T1-3", "coordinateXT1", "coordinateYT1", "coordinateXT3", "coordinateYT3"],
                  axis=1, inplace=True)

    return df


@logger.catch(level='DEBUG')
def geobd_gdis_data(df_input, df_exceptions, dict_parameters, log_user, progress_bar):
    """
    Функция обработки данных ГДИС из выгрузки ГеоБД

    :param df_exceptions: DataFrame исключенных скважин в ходе подготовки к расчету
    :param df_input: DataFrame, полученный путем считывания исходного файла со скважинами
    :param dict_parameters: словарь с параметрами расчета
    :param log_user: сигнал для передачи сообщения пользователю в окно логирования
    :param progress_bar: сигнал передачи значения в линию прогресса текущей задачи
    :return: DataFrame очищенный от скважин, на которых проводились ГДИС не ранее указанной даты
    """

    progress_bar.emit(0)
    logger.info('Upload GeoBD GDIS table')
    log_user.emit("Открытие листа с данными по исследованиям")

    app1 = xw.App(visible=False)
    gdis_wb = xw.Book(os.path.join(get_path(), "input", dict_parameters['data_file']))
    gdis_sheet = gdis_wb.sheets['ГДИС']
    # create list with names of cells in column Pпл на ВНК
    list_cells = gdis_sheet[
        f'L3:L{gdis_sheet['B1'].expand().last_cell.address.split('$')[-1]}']
    list_required_colors = ["RED", "GREEN"]

    colors = dict((
        ((196, 2, 51), "RED"),
        ((255, 165, 0), "ORANGE"),
        ((255, 205, 0), "YELLOW"),
        ((0, 128, 0), "GREEN"),
        ((0, 0, 255), "BLUE"),
        ((127, 0, 255), "VIOLET"),
        ((0, 0, 0), "BLACK"),
        ((255, 255, 255), "WHITE")))
    progress_bar.emit(33)

    # check that first cell in correct format
    if gdis_sheet['A1'].value == '№ п/п':
        log_user.emit("Разделение исследований на категории достоверное/недостоверное")
        for row_cell in list_cells:
            if min_color_diff(row_cell.font.color, colors)[-1] in list_required_colors:
                gdis_sheet[f'U{row_cell.address.split('$')[-1]}'].value = "результат достоверный"
                gdis_sheet[f'U{row_cell.address.split('$')[-1]}'].font.name = 'Times New Roman'
                gdis_sheet[f'U{row_cell.address.split('$')[-1]}'].font.color = row_cell.font.color
            else:
                gdis_sheet[f'U{row_cell.address.split('$')[-1]}'].value = "результат ненадежен"
                gdis_sheet[f'U{row_cell.address.split('$')[-1]}'].font.name = 'Times New Roman'
                gdis_sheet[f'U{row_cell.address.split('$')[-1]}'].font.color = (255, 0, 0)
        gdis_wb.save()
    else:
        # clearing sheet
        log_user.emit("Неверный формат таблицы с исследованиями")
        gdis_sheet.clear()
        gdis_wb.save()
    # close excel file
    gdis_wb.close()
    app1.kill()
    progress_bar.emit(67)

    try:
        # read data from sheet with pandas
        df_gdis = pd.read_excel(os.path.join(get_path(), "input", dict_parameters['data_file']), skiprows=[1],
                                sheet_name='ГДИС', dtype={"Дата испытания": str})
        # check empty dataframe
        if df_gdis.empty:
            log_user.emit("Лист с данными по исследованиям пуст")
            return df_input, df_exceptions
    except ValueError:
        # wrong type of data error and return origin dataframe
        logger.info('Sheet with name "ГДИС" not found in data file')
        log_user.emit("Лист с данными по исследованиям не найден")
        return df_input, df_exceptions
    # check parameter of date last GDIS
    if not (dict_parameters['gdis_option'] is None):
        dict_rename = {
            'Скважина': 'Скважина',
            'Пласт ОИС': 'Пласты',
            'Вид исследования': 'Вид исследования',
            'Дата испытания': 'Начальная дата',
            'Дата окончания': 'Дата окончания',
            'Качество исследования': 'Оценка',
        }

        df_gdis = df_gdis[df_gdis['Качество исследования'] == 'результат достоверный']
        df_gdis = df_gdis.fillna(0)
        df_gdis['Общее время исслед.'] = df_gdis['Общее время исслед.'].apply(lambda x: float(str(x).replace(",", ".")))
        df_gdis = df_gdis[df_gdis['Общее время исслед.'] > 24].reset_index(drop=True)
        df_gdis['Дата испытания'] = df_gdis['Дата испытания'].apply(lambda x: parseDate(str(x), dayfirst=True))
        # df_gdis['Дата испытания'] = df_gdis['Дата испытания'].apply(
        #     lambda x: str(x).replace("/", ".") if str(x).replace("/", ".") is not np.nan else str(x))
        df_gdis['Дата окончания'] = (pd.to_datetime(df_gdis['Дата испытания'], dayfirst=True)
                                     + df_gdis['Общее время исслед.'].apply(lambda x: timedelta(hours=x)))
        df_gdis = df_gdis[
            ['Скважина', 'Пласт ОИС', 'Вид исследования', 'Дата испытания', 'Дата окончания', 'Качество исследования']]
        df_gdis.columns = dict_rename.values()

        log_user.emit("Подготовка данных об исследованиях")
        df_gdis = gdis_preparing(df_gdis, df_input['wellName'], dict_parameters['gdis_option'])

        # drop wells by horizon gdis
        objects = df_gdis.groupby(['wellName'])['workHorizon'].apply(lambda x: set(x.explode()))
        df_input = df_input.apply(lambda x: drop_wells_by_gdis(x, objects), axis=1)
        df_exceptions = pd.concat([df_exceptions, df_input[df_input['workHorizon'] == '']],
                                  axis=0, sort=False).reset_index(drop=True)
        df_exceptions.loc[df_exceptions['wellNet'].isnull(), 'wellNet'] = 'Исключена по ГДИС'
        df_input = df_input[df_input['workHorizon'] != '']
        progress_bar.emit(100)
        return df_input, df_exceptions

    else:
        logger.info('Incorrect data of GDIS GeoBD')
        log_user.emit("ГДИС не учтены. Дата последнего актуального исследования не указана или неверный формат данных")
        progress_bar.emit(100)
        return df_input, df_exceptions


@logger.catch(level='DEBUG')
def ngt_gdis_data(df_input, df_exceptions, dict_parameters, log_user, progress_bar):
    """
    Загрузка данных по проведенным ГДИС на месторождении и удаление из входных данных
    скважин, на которых проводились исследования начиная с введенной пользователем даты по сей день

    :param df_exceptions: DataFrame исключенных скважин в ходе подготовки к расчету
    :param df_input: DataFrame, полученный путем считывания исходного файла со скважинами
    :param dict_parameters: словарь с параметрами расчета
    :param log_user: сигнал для передачи сообщения пользователю в окно логирования
    :param progress_bar: сигнал передачи значения в линию прогресса текущей задачи
    :return: DataFrame очищенный от скважин, на которых проводились ГДИС не более n лет назад
    """

    progress_bar.emit(0)
    logger.info("Upload NGT GDIS table")
    log_user.emit("Чтение таблицы исследований из NGT")
    try:

        df_gdis = pd.read_excel(os.path.join(get_path(), "input", dict_parameters['data_file']),
                                skiprows=[0], sheet_name='ГДИС')
        progress_bar.emit(33)
        if df_gdis.empty:
            log_user.emit("Лист с данными по исследованиям пуст")
            progress_bar.emit(100)
            return df_input, df_exceptions
    except ValueError:
        log_user.emit("Лист с данными по исследованиям не найден")
        logger.info('Sheet with name "ГДИС" not found in data file')
        progress_bar.emit(100)
        return df_input, df_exceptions

    # get input_output dataframes
    if not (dict_parameters['gdis_option'] is None):

        df_gdis = df_gdis[['Скважина', 'Пласты', 'Вид исследования', 'Начальная дата', 'Дата окончания', 'Оценка']]
        log_user.emit("Подготовка данных об исследованиях")
        df_gdis = gdis_preparing(df_gdis, df_input['wellName'], dict_parameters['gdis_option'])
        progress_bar.emit(67)

        # drop wells by horizon gdis
        objects = df_gdis.groupby(['wellName'])['workHorizon'].apply(lambda x: set(x.explode()))
        df_input = df_input.apply(lambda x: drop_wells_by_gdis(x, objects), axis=1)
        df_exceptions = pd.concat([df_exceptions, df_input[df_input['workHorizon'] == '']],
                                  axis=0, sort=False).reset_index(drop=True)
        df_exceptions.loc[df_exceptions['wellNet'].isnull(), 'wellNet'] = 'Исключена по ГДИС'
        df_input = df_input[df_input['workHorizon'] != '']
        progress_bar.emit(100)

        return df_input, df_exceptions

    else:
        logger.info('Incorrect date of GDIS')
        log_user.emit("ГДИС не учтены. Дата последнего актуального исследования не указана")
        progress_bar.emit(100)
        return df_input, df_exceptions


@logger.catch(level='DEBUG')
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
    # create dict for rename dataframe
    dict_names_gdis = {
        'Скважина': 'wellName',
        'Пласты': 'workHorizon',
        'Вид исследования': 'type_of_research',
        'Начальная дата': 'begin_of_research',
        'Дата окончания': 'end_of_research',
        'Оценка': 'quality'
    }

    # list with status low quality of research
    LOW = ["результат ненадежен", "низкая"]
    # rename dataframe columns
    df_gdis.columns = dict_names_gdis.values()
    df_gdis = df_gdis.fillna(0)
    df_gdis = df_gdis.astype({'wellName': str, 'workHorizon': str, 'quality': str})
    # leave in gdis dataframe only well that input dataframe contains
    df_gdis = df_gdis[df_gdis['wellName'].isin(list(input_wells.explode().unique()))]
    # delete wells with no data about research time
    df_gdis = df_gdis[(df_gdis['end_of_research'] != 0) & (df_gdis['begin_of_research'] != 0)]

    df_gdis['begin_of_research'] = pd.to_datetime(df_gdis['begin_of_research'])
    df_gdis['end_of_research'] = pd.to_datetime(df_gdis['end_of_research'])
    try:
        # delete well with date of end research later than input date parameter 'year'
        df_gdis = df_gdis[df_gdis['end_of_research'] >= pd.to_datetime(year, format='%d.%m.%Y')]
    except ValueError:
        raise ValueError(
            f'Введена некорректная дата ГДИС {year}. Введите в параметрах расчета дату в формате ДД.ММ.ГГГГ')
    # split work objects by ;
    df_gdis['workHorizon'] = list(map(lambda x: x.replace(" ", "").split(";"), df_gdis['workHorizon']))
    df_gdis['type_of_research'] = list(map(lambda x: x.replace(" ", "").split("+"), df_gdis['type_of_research']))
    # delete wells if their quality of research is low
    df_gdis = df_gdis[~df_gdis['quality'].isin(LOW)]
    # calculate the duration of research
    df_gdis['time_of_research'] = df_gdis['end_of_research'] - df_gdis['begin_of_research']
    # delete well with null duration of research
    df_gdis = df_gdis[df_gdis['time_of_research'] != timedelta(0)]

    return df_gdis


@logger.catch(level='DEBUG')
def drop_wells_by_gdis(input_row, gdis_objects):
    """
    Функция удаляет объекты для каждой скважины, если по ним проводились ГДИС

    :param input_row: текущая строка из входного DataFrame
    :param gdis_objects: Series из объектов на которых проводились ГДИС, индексами являются скважины
    :return: возвращает измененную строку DataFrame или ту же строку, если скважины не оказалось в gdis_object Series
    """
    # set of well objects in input dataframe
    set_input_objects = set(input_row['workHorizon'].split(', '))
    try:
        # leave in gdis objects only objects that contains in input dataframe
        set_gdis_objects = gdis_objects[input_row.wellName]
    except KeyError:
        return input_row
    # objects that haven't research
    input_row['workHorizon'] = ', '.join(str(e) for e in list(set_input_objects - set_gdis_objects))
    return input_row


@logger.catch(level='DEBUG')
def preparing_reservoir_properties(dict_parameters, path, log_user, progress_bar):
    """
    Подготовка PVT свойств из справочника PVT и далее запись в .json файл
    для быстрого дотсупа к свойствам объектов в процессе расчета

    :param dict_parameters: словарь с параметрами расчета
    :param path: путь к корневой папке
    :param log_user: сигнал для передачи сообщения пользователю в окно логирования
    :param progress_bar: сигнал передачи значения в линию прогресса текущей задачи
    :return: сохраняет словарь в корневую папку в виде json файла со свойствами месторождений
    """

    progress_bar.emit(0)
    application_path = get_path()
    try:
        log_user.emit("Чтение листа с PVT свойствами всех месторождений")
        df_property = pd.read_excel(os.path.join(application_path, "input", dict_parameters['data_file']),
                                    skiprows=[0],
                                    sheet_name='PVT', decimal=',')
        if df_property.empty:
            logger.info('Not found PVT properties data')
            log_user.emit("Лист с PVT свойствами пуст. Загрузите необходимые данные и запустите расчет снова")
            progress_bar.emit(100)
            sys.exit()
    except ValueError:
        logger.info('Sheet with name "PVT" not found in data file')
        log_user.emit("Лист с PVT свойствами не найден. Загрузите необходимые данные и запустите расчет снова")
        progress_bar.emit(100)
        sys.exit()
    progress_bar.emit(20)
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
    # delete spaces in columns PVT dataframe
    df_property.columns = df_property.columns.str.strip()
    # choose the required columns PVT dataframe for old and new table format
    logger.info("Rename PVT table columns")
    try:
        df_property = df_property[['Месторождение', 'Пласт OIS', 'Рпл.нач., кгс/см2          (карты изобар)',
                                   'μн. в пл. усл., сП', 'μв. в пл. усл., сП',
                                   'm,     %', 'β, 1/атм*10-5 породы', 'β, 1/атм*10-5 нефть',
                                   'β, 1/атм*10-5 вода', 'μг., сП в пласт. усл.', 'Степень Krw  (для ОФП)',
                                   'Степень для функции Krw (доп)  (для ОФП)', 'Степень Kro  (для ОФП)',
                                   'Степень для функции Kro (доп) (для ОФП)', 'Swo (для ОФП)', 'Swk  (для ОФП)',
                                   'Krwk  (для ОФП)', 'Krok  (для ОФП)', 'Кпрон (средняя) по нефти']]
    except KeyError:
        df_property = df_property[['Месторождение', 'Пласт OIS', 'Рпл.нач., кгс/см2          (карты изобар)',
                                   'μн. в пл. усл., сП', 'μв. в пл. усл., сП',
                                   'm,     %', 'β, 1/атм*10-5 породы', 'β, 1/атм*10-5 нефть',
                                   'β, 1/атм*10-5 вода', 'μг., сП в пласт. усл.', 'Степень Krw:',
                                   'Степень для функции Krw (доп):', 'Степень Kro:',
                                   'Степень для функции Kro (доп):', 'Swo', 'Swk',
                                   'Krwk', 'Krok', 'Кпрон']]

    df_property.columns = dict_names_prop.values()
    progress_bar.emit(40)
    logger.info("Delete spaces in all dataframe columns besides oilfield and reservoir columns")
    log_user.emit("Подготовка данных PVT свойств месторождений")
    for i in df_property.columns:
        # delete spaces in all dataframe columns besides oilfield and reservoir columns
        df_property[i] = list(map(lambda x: str(x).strip(), df_property[i]))
        if i != 'oilfield' and i != 'reservoir':
            df_property[i] = list(map(lambda x: float(str(x).replace(',', '.')), df_property[i]))
    df_property['oilfield'] = df_property['oilfield'].map(str.upper)
    # group dataframe by oilfield and reservoir columns and calculate mean properties
    df_property = df_property.groupby(by=['oilfield', 'reservoir'], as_index=False).mean()
    df_property['horizon'] = list(map(lambda x, y: f'{x}__{y}', df_property.oilfield, df_property.reservoir))
    df_property['Sno'] = list(map(lambda x: round(1 - x, 3), df_property['Swk']))
    df_property[['oilfield', 'reservoir']] = df_property[['oilfield', 'reservoir']].astype('str')
    df_property = df_property.fillna(0)
    progress_bar.emit(60)

    # create list of unique names oilfield-reservoir
    logger.info("Create list of unique names oilfield-reservoir")
    list_oilfield_res = list(df_property['horizon'].explode().unique())
    list_properties = ['porosity', 'pressure', 'oil_compr', 'water_copmr', 'rock_compr', 'oil_visc',
                       'water_visc', 'gas_visc', 'K_wmax', 'K_omax', 'Swo', 'Swk', 'Sno',
                       'Krw_degree', 'Krw_func', 'Kro_degree', 'Kro_func', 'K_abs']
    list_oilfield = list(df_property['oilfield'].explode().unique())

    # writing properties in dictionary by propetry dataframe as olifield/object/properties
    logger.info("Writing properties in dictionary by propetry dataframe as olifield/object/properties")
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
    progress_bar.emit(80)

    # calculating mean properties by objects for each olifield
    logger.info("Calculating mean properties by objects for each olifield")
    for oilfield in list_oilfield:
        dict_mean_prop = dict.fromkeys(list_properties)
        for prop in list_properties:
            dict_mean_prop[prop] = df_property[df_property['oilfield'] == oilfield][prop].mean()
        dict_PVT[oilfield]['DEFAULT_OBJ'] = dict_mean_prop
    # writing calculated properties to json file
    logger.info("Writing calculated properties to json file")
    with open(path, 'w', encoding='UTF-8') as file:
        json_string = json.dumps(dict_PVT, default=lambda o: o.__dict__, ensure_ascii=False, sort_keys=True,
                                 indent=2)
        file.write(json_string)
    progress_bar.emit(100)

    pass


@logger.catch(level='DEBUG')
def get_exception_wells(dict_parameters, sheet, log_user):
    """
    Загрузка скважин, которые необходимо исключить из ОС

    :param sheet: имя листа в исходном файле Excel
    :param dict_parameters: словарь с параметрами расчета
    :param log_user: сигнал для передачи сообщения пользователю в окно логирования
    :return: возвращает список обязательных для включения в ОС скважин
    """
    application_path = get_path()

    try:
        # read first row of file
        first_row = pd.read_excel(os.path.join(application_path, "input", dict_parameters['data_file']), header=None,
                                  sheet_name='Исключения', nrows=1)
        if first_row.loc[0][0] == "NSKV":
            df_exception = pd.read_excel(os.path.join(application_path, "input", dict_parameters['data_file']),
                                         header=0,
                                         sheet_name=sheet)
        else:
            df_exception = pd.read_excel(os.path.join(application_path, "input", dict_parameters['data_file']),
                                         header=None,
                                         sheet_name=sheet)
        df_exception.columns = ["wellName", "workHorizon"]

        if df_exception.empty:
            return pd.DataFrame(columns=["wellName", "workHorizon"])
        df_exception[["wellName", "workHorizon"]] = df_exception[["wellName", "workHorizon"]].astype(str)
        df_exception["wellName"] = df_exception["wellName"].apply(lambda x: x.replace("_T3", ""))
        list_uniq_wells = list(df_exception["wellName"].explode().unique())
        for well in list_uniq_wells:
            objects = list(df_exception[df_exception["wellName"] == well]["workHorizon"].explode().unique())
            df_exception.loc[df_exception["wellName"] == well, "workHorizon"] = ", ".join(objects)
        df_exception = df_exception.drop_duplicates(subset=["wellName"]).reset_index(drop=True)
    except Exception as e:
        logger.info(f"Sheet '{sheet}' not found in data file")
        logger.info(f"Error reading exception sheet: {e}")
        log_user.emit(f"Лист '{sheet}' не найден")
        return pd.DataFrame(columns=["wellName", "workHorizon"])

    return df_exception


@logger.catch(level='DEBUG')
def get_necessarily_wells(dict_parameters, sheet, log_user):
    """
    Загрузка скважин, обязательных для включения в ОС

    :param sheet: имя листа в исходном файле Excel
    :param dict_parameters: словарь с параметрами расчета
    :param log_user: сигнал для передачи сообщения пользователю в окно логирования
    :return: возвращает список обязательных для включения в ОС скважин
    """
    application_path = get_path()
    try:
        logger.info(f"Trying read sheet '{sheet}'")
        log_user.emit(f"Чтение листа '{sheet}'")
        df_necessarily = pd.read_excel(os.path.join(application_path, "input", dict_parameters['data_file']),
                                       header=None,
                                       sheet_name=sheet)
        if df_necessarily.empty:
            logger.info(f"Empty sheet '{sheet}'")
            log_user.emit(f"Нет данных на листе '{sheet}'")
            return []
    except ValueError:
        logger.info(f"Sheet '{sheet}' not found in data file")
        log_user.emit(f"Лист '{sheet}' не найден")
        return []

    df_necessarily[0] = df_necessarily[0].astype(str)
    # list unique well names for exception
    list_exception = list(df_necessarily[0].explode().unique())

    return list_exception


@logger.catch(level='DEBUG')
def fonds_for_calc(df_horizon, script, percent, cover_criteria, mean_oilrate_option, percent_oilrate):
    """
    Подготовка пьезометров, нагнетательных и добывающих скважин для расчета с учетом списка приоритетных к исследованию

    :param df_horizon: DataFrame скважин выделенных на текущий объект расчета
    :param script: сценарий расчета
    :param percent: процент расстояния между точками T1 и T3 необходимый для включения скважины в зону исследования
    :param cover_criteria: параметр учета процента расстояния между точками T1 и T3 скважины
    :param mean_oilrate_option: параметр учета среднего дебита нефти по объекту
    :param percent_oilrate: процент от среднего дебита нефти по объекту
    :return: Подготовленные DataFrame 3-х фондов, DataFrame приоритетных скважин, DataFrame скважин, охваченных
             приоритетными и средний дебит по объекту расчета
    """
    df_necessarily = df_horizon[df_horizon['num_of_research']]
    if script == 'optimize':
        # добавление столбца скважин, охваченных приоритетными для оптимальной сетки
        df_necessarily['intersection'] = list(
            map(lambda x, y: check_intersection_area(x, df_horizon[(df_horizon['fond'] == 'ДОБ') &
                                                                   (df_horizon['num_of_research']) & (
                                                                               df_horizon['wellName'] != y)],
                                                     percent, cover_criteria), df_necessarily['AREA'],
                df_necessarily['wellName']))
    else:
        # добавление столбца скважин, охваченных приоритетными для регулярной сетки
        df_necessarily['intersection'] = list(map(lambda x, y:
                                                  check_intersection_area(x, df_horizon[
                                                      (df_horizon['num_of_research']) & (df_horizon['wellName'] != y)],
                                                                          percent, cover_criteria),
                                                  df_necessarily['AREA'], df_necessarily['wellName']))
    if not df_necessarily.empty:
        # скважины охватывают сами себя, поэтому для дальнейших расчетов, необходимо удалить из столбца пересечений лишние
        df_necessarily['intersection'] = df_necessarily.apply(
            lambda x: [y for y in x['intersection'] if y != x['wellName']], axis=1)
    #  подсчет кол-ва охваченных скважин
    df_necessarily['number'] = df_necessarily['intersection'].apply(lambda x: len(set(x)))
    # инициализация списка скважин приоритетных к включению в ОС
    list_necessarily = list(set(df_necessarily['wellName'].explode().unique()))
    # инициализация списка скважин, охваченных приоритетными к включению в ОС
    list_intersection_necessarily = list(set([x for x in list(df_necessarily['intersection'].explode().unique())
                                              if x == x]))
    # DataFrame с исключенными скважинами по результатам работы данной функции
    df_exception = df_horizon[df_horizon['wellName'].isin(list_intersection_necessarily)]
    df_exception['wellNet'] = 'Охвачена приоритетными скважинами'

    df_prod_wells = df_horizon.loc[(df_horizon['fond'] == 'ДОБ') &
                                   (~df_horizon['wellName'].isin(list_intersection_necessarily + list_necessarily))]

    # выделение продуктивных, нагнетательных и исследуемых скважин для объекта, дебит нефти которых не превышает
    # среднего дебита нефти по объекту
    mean_oilrate = 0
    if mean_oilrate_option and (df_prod_wells.shape[0] > 0):
        mean_oilrate = df_prod_wells['oilRate'].mean()
        df_exception = pd.concat([df_exception, df_prod_wells[
            (df_prod_wells['oilRate'] >= mean_oilrate * percent_oilrate / 100) & (
                    (df_prod_wells['gasStatus'] == 'нефтяная') |
                    (df_prod_wells['gasStatus'] == 'газоконденсатная'))]], axis=0, sort=False).reset_index(drop=True)
        df_exception.loc[df_exception['wellNet'].isnull(), 'wellNet'] = 'Исключена по среднему дебиту'
        df_prod_wells = df_prod_wells[~((df_prod_wells['oilRate'] > mean_oilrate * percent_oilrate / 100) &
                                        ((df_prod_wells['gasStatus'] == 'нефтяная') |
                                         (df_prod_wells['gasStatus'] == 'газоконденсатная')))]

    # удаление из расчетного DataFrame скважин, охваченных приоритетными к исследованию
    df_horizon = df_horizon[~df_horizon['wellName'].isin(list_intersection_necessarily + list_necessarily)]
    #  Выделение нагнетательного и пьезометрического фондов для расчета
    df_piez_wells = df_horizon.loc[df_horizon['fond'] == 'ПЬЕЗ']
    df_inj_wells = df_horizon.loc[df_horizon['fond'] == 'НАГ']

    return df_prod_wells, df_piez_wells, df_inj_wells, df_necessarily, df_exception, mean_oilrate
