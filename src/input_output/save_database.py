import sqlite3 as sql
import pandas as pd
from loguru import logger
from tqdm import tqdm
from .save_excel import get_report


@logger.catch(level='DEBUG')
def results_to_db(dict_result, dict_parameters, path_database):
    """
    Запись результатов в базу данных
    :param dict_result: словарь, по ключам которого содержится результирующий DataFrame для каждого контура
    :param dict_parameters: словарь с параметрами расчета
    :param path_database: путь для сохранения базы данных с результатами
    :return:
    """
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
    db_result = sql.connect(path_database)

    for key, value in tqdm(dict_result.items(), "Write regular mesh to excel file", position=0, leave=True,
                           colour='white', ncols=80):
        name = str(key).replace("/", " ")
        # reduce name of Excel sheet to 31 characters if it's too long
        if len(name) > 31:
            name = name.split(' k=')[0][:31 - len(' k=' + name.split(' k=')[-1])] + ' k=' + name.split(' k=')[-1]

        df = value[0].copy()
        df['num_of_research'] = df['num_of_research'].apply(lambda x: int(x) + 1)
        df.drop(columns=['POINT3', 'POINT', 'GEOMETRY', 'limit_oilrate', 'min_dist', 'gasStatus', 'AREA'],
                axis=1, inplace=True)
        df = df[dict_rename.keys()]
        df['intersection'] = df['intersection'].fillna('')
        df['intersection'] = list(
            map(lambda x: " ".join(str(y) for y in x) if type(x) != str else x, df["intersection"]))
        df.columns = dict_rename.values()
        df['Дата'] = pd.to_datetime(df['Дата'])
        logger.info(f'Write to database table with name: {name}')
        df.to_sql(name=name.replace('-', '/'), con=db_result, if_exists='replace')

    logger.info('Getting report table')
    df_report = get_report(dict_result)

    logger.info('Writing report table to database')
    df_report.to_sql(name='report', con=db_result, if_exists='replace')
    pd.DataFrame.from_dict(dict_parameters).to_sql(name='parameters', con=db_result, if_exists='replace')
    db_result.commit()
    db_result.close()

    pass
