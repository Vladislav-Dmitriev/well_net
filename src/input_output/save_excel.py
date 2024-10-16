import sqlite3 as sql
import os
import pandas as pd
import xlwings as xw
from loguru import logger
from tqdm import tqdm
from src.calculation.support_functions import get_path


@logger.catch(level='DEBUG')
def results_to_excel(dict_result, dict_parameters, path_database):
    """
    Запись результатов расчета в Excel файл
    :param path_database: путь для сохранения базы данных с результатами
    :param dict_parameters: словарь с параметрами расчета
    :param dict_result: словарь, по ключам которого содержится результирующий DataFrame для каждого контура
    :return: функция сохраняет файл в указанную директорию
    """
    if dict_parameters['calculation_scenario'] == 'optimize':
        script_folder = os.path.join(get_path(), 'output', 'Оптимальная сетка')
        saving_path = os.path.join(get_path(), 'output', 'Оптимальная сетка', 'Оптимальная сетка.xlsx')
    else:
        script_folder = os.path.join(get_path(), 'output', 'Регулярная сетка')
        saving_path = os.path.join(get_path(), 'output', 'Регулярная сетка', 'Регулярная сетка.xlsx')
    dict_rename = {
        'wellName': '№ скважины',
        'nameDate': 'Дата',
        'workMarker': 'Характер работы',
        'wellStatus': 'Состояние',
        'oilfield': 'Месторождение',
        'workHorizon': 'Объекты работы',
        'wellCluster': 'Куст',
        'coordinateX': 'Координата X',
        'coordinateX3': 'Координата забоя Х (по траектории)',
        'coordinateY': 'Координата Y',
        'coordinateY3': 'Координата забоя Y (по траектории)',
        'oilRate': 'Дебит нефти (ТР), т/сут',
        'fluidRate': 'Дебит жидкости (ТР), м3/сут',
        'gasRate': 'Дебит природного газа, тыс.м3/сут',
        'injectivity': 'Приемистость (ТР), м3/сут',
        'injectivity_day': 'Приемистость (по суточным), м3/сут',
        'water_cut': 'Обводненность (ТР), % (объём)',
        'exploitation': 'Способ эксплуатации',
        'condRate': 'Дебит конденсата газа, т/сут',
        'well type': 'Тип скважины',
        'fond': 'Фонд скважины',
        'num_of_research': 'Количество исследований в год',
        'intersection': 'Пересечения со скважинами',
        'number': 'Кол-во пересечений',
        'mean_radius': 'Средний радиус по объекту, м',
        'time_coef': 'Коэффициент для расчет времени исследования',
        'k': 'Проницаемость, мД',
        'gas_visc': 'Вязкость газа в пластовых условиях, сПз',
        'pressure': 'Начальное пластовое давление (карты изобар), атм',
        'default_count': 'Объектов по умолчанию',
        'obj_count': 'Объектов всего',
        'percent_of_default': 'Процент объектов со свойствами по умолчанию',
        'current_horizon': 'Объект расчета',
        'research_time': 'Время исследования, сут',
        'oil_loss': 'Потери нефти, т',
        'gas_loss': 'Потери газа, тыс. м3',
        'injection_loss': 'Потери закачки, м3',
        'coverage_percentage': 'Процент охвата площади объекта',
        'percent_piez_wells': 'Доля пьезометров в опорной сети',
        'percent_inj_wells': 'Доля нагнетательных в опорной сети',
        'percent_prod_wells': 'Доля добывающих в опорной сети',
        'percent_gas_wells': 'Доля газовых добывающих скважин в опорной сети',
        'year_of_survey': 'Год исследования',
        'mean_oilrate': 'Средний дебит нефти по объекту, т/сут',
        'wellNet': 'Статус по опорной сети'
    }
    # create database for result tables
    if path_database == '':
        db_result = sql.connect(f'{get_path()}\\output\\wellnet_result.db')
    else:
        db_result = sql.connect(path_database)

    # create new excel file for results
    app1 = xw.App(visible=False)
    new_wb = xw.Book()

    for key, value in tqdm(dict_result.items(), "Write regular mesh to excel file", position=0, leave=True,
                           colour='white', ncols=80):
        name = str(key).replace("/", " ")
        # reduce name of Excel sheet to 31 characters if it's too long
        if len(name) > 31:
            name = name.split(' k=')[0][:31 - len(' k=' + name.split(' k=')[-1])] + ' k=' + name.split(' k=')[-1]

        if f"{name}" in new_wb.sheets:
            xw.Sheet[f"{name}"].delete()

        logger.info(f'Create new sheet in Excel with name: {name}')
        new_wb.sheets.add(f"{name}")

        sht = new_wb.sheets(f"{name}")

        df = value[0].copy()
        df['num_of_research'] = df['num_of_research'].apply(lambda x: int(x) + 1)
        df.drop(columns=['POINT3', 'POINT', 'GEOMETRY', 'limit_oilrate', 'min_dist', 'gasStatus', 'AREA'],
                axis=1, inplace=True)
        df = df[dict_rename.keys()]
        df['intersection'] = df['intersection'].fillna('')
        df['intersection'] = list(
            map(lambda x: " ".join(str(y) for y in x) if type(x) != str else x, df["intersection"]))
        df.columns = dict_rename.values()
        sht.range('A1').options().value = pd.DataFrame(df)
        df['Дата'] = pd.to_datetime(df['Дата'])
        df.to_sql(name=name.replace('-', '/'), con=db_result, if_exists='replace')

    logger.info('Getting report table')
    df_report = get_report(dict_result)
    if "report" in new_wb.sheets:
        xw.Sheet["report"].delete()
    new_wb.sheets.add("report")
    sht = new_wb.sheets("report")
    sht.range('A1').options().value = df_report
    logger.info('Saving results in excel file')

    try:
        os.mkdir(script_folder)
    except OSError:

        pass
    new_wb.save(saving_path)
    # End print
    app1.kill()
    df_report.to_sql(name='report', con=db_result, if_exists='replace')
    db_result.commit()
    db_result.close()

    return path_database


@logger.catch(level='DEBUG')
def get_report(dict_result):
    """
    Функция для создания краткого отчета по всем контурам с разными коэффициентами для радиусов охвата
    :param dict_result: словарь с результатами расчетов по всем объектам
    :return: возвращает DataFrame с отчетом по каждому контуру с определенным коэффициентом увеличения радиуса
    """
    dict_names_report = {'contour_k': 'Сценарий',
                         'obj_count': 'Кол-во объектов',
                         'mean_rad': 'Средний радиус',
                         'mean_time': 'Среднее время исследования',
                         'piez_count': 'Кол-во пьезометров',
                         'inj_count': 'Кол-во нагн',
                         'prod_count': 'Кол-во доб',
                         'well_quantity0': 'Кол-во исслед. скв. 1 год',
                         'well_quantity1': 'Кол-во исслед. скв. 2 год',
                         'well_quantity2': 'Кол-во исслед. скв. 3 год',
                         'research_wells0': 'Охваченные исследованиями 1 год',
                         'research_wells1': 'Охваченные исследованиями 2 год',
                         'research_wells2': 'Охваченные исследованиями 3 год',
                         'oil_loss0': 'Потери нефти 1 год, т',
                         'oil_loss1': 'Потери нефти 2 год, т',
                         'oil_loss2': 'Потери нефти 3 год, т',
                         'injection_loss0': 'Потери закачки жидкости 1 год, м3',
                         'injection_loss1': 'Потери закачки жидкости 2 год, м3',
                         'injection_loss2': 'Потери закачки жидкости 3 год, м3',
                         'gas_loss0': 'Потери по добыче газа 1 год, тыс.м3',
                         'gas_loss1': 'Потери по добыче газа 2 год, тыс.м3',
                         'gas_loss2': 'Потери по добыче газа 3 год, тыс.м3',
                         'percent_of_default': 'Процент объектов по умолчанию'}

    dict_report = {}

    for key, value in tqdm(dict_result.items(), "Preparing report", position=0, leave=True,
                           colour='white', ncols=80):
        df = value[0]
        df = df[df['wellNet'] == 'Выбрана в опорную сеть']

        dict_report['contour_k'] = dict_report.get('contour_k', []) + [key]
        dict_report['obj_count'] = dict_report.get('obj_count', []) + [len(set(df['workHorizon'].explode().unique()))]
        dict_report['mean_rad'] = dict_report.get('mean_rad', []) + [df['mean_radius'].mean()]
        dict_report['mean_time'] = dict_report.get('mean_time', []) + [df['research_time'].mean()]
        dict_report['piez_count'] = dict_report.get('piez_count', []) + [len(df[df['fond'] == 'ПЬЕЗ'])]
        dict_report['inj_count'] = dict_report.get('inj_count', []) + [len(df[df['fond'] == 'НАГ'])]
        dict_report['prod_count'] = dict_report.get('prod_count', []) + [len(df[df['fond'] == 'ДОБ'])]

        dict_report['well_quantity0'] = dict_report.get('well_quantity0', []) + [df[df['year_of_survey'] == 0].shape[0]]
        dict_report['well_quantity1'] = (dict_report.get('well_quantity1', []) +
                                         [df[df['year_of_survey'] == 1].shape[0]])
        dict_report['well_quantity2'] = (dict_report.get('well_quantity2', []) +
                                         [df[df['year_of_survey'] == 2].shape[0]])

        dict_report['research_wells0'] = (dict_report.get('research_wells0', []) +
                                          [len(set(df[df['year_of_survey'] == 0]['intersection'].explode().unique()))])
        dict_report['research_wells1'] = dict_report.get('research_wells1', []) + [
            len(set(df[df['year_of_survey'] == 1]['intersection'].explode().unique()))]
        dict_report['research_wells2'] = dict_report.get('research_wells2', []) + [
            len(set(df[df['year_of_survey'] == 2]['intersection'].explode().unique()))]
        # потери по добыче нефти
        dict_report['oil_loss0'] = dict_report.get('oil_loss0', []) + [df[df['year_of_survey'] == 0].oil_loss.sum()]
        dict_report['oil_loss1'] = dict_report.get('oil_loss1', []) + [df[df['year_of_survey'] == 1].oil_loss.sum()]
        dict_report['oil_loss2'] = dict_report.get('oil_loss2', []) + [df[df['year_of_survey'] == 2].oil_loss.sum()]
        # потери по закачке жидкости
        dict_report['injection_loss0'] = (dict_report.get('injection_loss0', []) +
                                          [df[df['year_of_survey'] == 0].injection_loss.sum()])
        dict_report['injection_loss1'] = (dict_report.get('injection_loss1', []) +
                                          [df[df['year_of_survey'] == 1].injection_loss.sum()])
        dict_report['injection_loss2'] = dict_report.get('injection_loss2', []) + [
            df[df['year_of_survey'] == 2].injection_loss.sum()]
        # потери по добыче газа
        dict_report['gas_loss0'] = (dict_report.get('gas_loss0', []) +
                                    [df[(df['year_of_survey'] == 0) & (df['fond'] == 'ДОБ')].gas_loss.sum()])
        dict_report['gas_loss1'] = (dict_report.get('gas_loss1', []) +
                                    [df[(df['year_of_survey'] == 1) & (df['fond'] == 'ДОБ')].gas_loss.sum()])
        dict_report['gas_loss2'] = (dict_report.get('gas_loss2', []) +
                                    [df[(df['year_of_survey'] == 2) & (df['fond'] == 'ДОБ')].gas_loss.sum()])

        dict_report['percent_of_default'] = (dict_report.get('percent_of_default', []) +
                                             [100 * df.default_count.sum() / df.obj_count.sum()])

    df_report = pd.DataFrame.from_dict(dict_report, orient='columns')
    # округление числовых столбцов DataFrame до 2 знаков после запятой
    df_report.rename(columns=dict_names_report, inplace=True)

    return df_report
