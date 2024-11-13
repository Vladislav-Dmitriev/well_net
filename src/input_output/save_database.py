import json
import os
import sqlite3 as sql
import pandas as pd
import shapely as spl
from loguru import logger
from tqdm import tqdm
from src.input_output.save_excel import get_report
from src.calculation.shapely_geometry import check_intersection_area


@logger.catch(level='DEBUG')
def results_to_db(dict_result, df_exceptions, dict_parameters, list_name_params, path_database, progress_bar):
    """
    Запись результатов в базу данных

    :param dict_result: dict - словарь, содержащий DataFrame результатов для каждого контура
    :param df_exceptions: DataFrame - исключенные из расчета скважины
    :param dict_parameters: dict - параметры расчета
    :param list_name_params: list - список имен параметров расчета
    :param path_database: str - путь к файлу базы данных для сохранения результатов
    :param progress_bar:
    """
    dict_rename = get_column_mappings()

    # Подготовка базы данных
    db_result = prepare_database(path_database)
    total_count_tables = len(dict_result)
    # Запись данных по контурам
    for i, (contour_name, data) in enumerate(tqdm(dict_result.items(), "Запись сетки в базу данных", position=0,
                                                  leave=True, colour='white', ncols=80, disable=True)):
        write_contour_data(contour_name, data, df_exceptions, dict_parameters, db_result, dict_rename)
        progress_bar.emit(int((i + 1) / total_count_tables * 100))

    # Запись итогового отчета
    save_report_to_db(db_result, dict_result, dict_parameters, list_name_params)

    db_result.commit()
    db_result.close()


@logger.catch(level='DEBUG')
def get_column_mappings():
    """
    Возвращает словарь для переименования колонок из стандартизированных имен в удобочитаемые имена

    :return: dict - словарь для переименования колонок
    """
    return {
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
        'GEOMETRY': 'GEOMETRY',
        'num_of_research': 'Кол-во исследований в год',
        'AREA': 'AREA',
        'intersection': 'Пересечения со скважинами',
        'number': 'Кол-во пересечений',
        'mean_radius': 'Средний радиус по объекту, м',
        'time_coef': 'Коэффициент для расчета времени исследования',
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
        'wellNet': 'Статус по опорной сети',
        'polygon': 'polygon'
    }


@logger.catch(level='DEBUG')
def prepare_database(path_database):
    """
    Создает и возвращает подключение к базе данных, удаляя старую версию базы, если она существует

    :param path_database: str - путь к файлу базы данных
    :return: sqlite3.Connection - подключение к базе данных
    """
    if os.path.exists(path_database):
        os.remove(path_database)
    return sql.connect(path_database)


def write_contour_data(contour_name, data, df_exceptions, dict_parameters, db_result, dict_rename):
    """
    Записывает данные по контуру в базу данных.

    :param contour_name: str - имя контура, используемое как имя таблицы
    :param data: tuple - данные контура в виде кортежа (DataFrame, объект контура)
    :param df_exceptions: DataFrame - данные исключенных скважин
    :param dict_parameters: dict - параметры расчета
    :param db_result: sqlite3.Connection - подключение к базе данных
    :param dict_rename: dict - словарь для переименования колонок
    """
    contour_name = format_name(contour_name)
    df, contour = data[0].copy(), data[1]

    # Исключенные скважины для текущего контура
    df_excluded = filter_exceptions(df_exceptions, contour, dict_parameters)

    # Обработка данных перед записью
    df = prepare_dataframe_for_db(df, df_excluded, contour, dict_rename)

    # Запись данных в таблицу базы данных
    logger.info(f'Запись в таблицу: {contour_name}')
    df.to_sql(name=contour_name, con=db_result, if_exists='replace')


@logger.catch(level='DEBUG')
def format_name(name):
    """
    Форматирует имя контура для использования в качестве имени таблицы, сокращая его до 31 символа при необходимости.

    :param name: str - оригинальное имя контура
    :return: str - отформатированное имя таблицы
    """
    name = str(name).replace("/", " ")
    return name[:31] if len(name) > 31 else name


@logger.catch(level='DEBUG')
def filter_exceptions(df_exceptions, contour, dict_parameters):
    """
    Фильтрует исключенные скважины для текущего контура, если контур указан.

    :param df_exceptions: DataFrame - данные исключенных скважин
    :param contour: объект контура (Polygon или None) - контур для фильтрации скважин
    :param dict_parameters: dict - параметры расчета для фильтрации
    :return: DataFrame - отфильтрованные данные исключений
    """
    if contour is None:
        return df_exceptions.copy()
    intersecting_wells = check_intersection_area(
        contour, df_exceptions, dict_parameters['percent'], dict_parameters['calc_option']
    )
    return df_exceptions[df_exceptions['wellName'].isin(intersecting_wells)]


@logger.catch(level='DEBUG')
def prepare_dataframe_for_db(df, df_excluded, contour, dict_rename):
    """
    Подготавливает DataFrame перед записью в базу данных.

    :param df: DataFrame - исходные данные контура
    :param df_excluded: DataFrame - исключенные скважины для текущего контура
    :param contour: объект контура (Polygon или None) - контур для добавления геометрии
    :param dict_rename: dict - словарь для переименования колонок
    :return: DataFrame - подготовленные данные для записи
    """
    df['num_of_research'] += 1
    df.drop(columns=['POINT3', 'POINT', 'limit_oilrate', 'min_dist', 'gasStatus'], inplace=True)

    # Объединение с исключенными скважинами
    df = pd.concat([df, df_excluded], ignore_index=True).reset_index(drop=True)

    df['intersection'] = df['intersection'].fillna('')
    df[['intersection']] = df[['intersection']].astype(str)
    df['AREA'] = df['AREA'].apply(lambda x: spl.to_geojson(x) if isinstance(x, spl.Polygon) else x)
    df['GEOMETRY'] = df.apply(lambda row: json.dumps(
        spl.geometry.mapping(row['GEOMETRY']) if pd.notna(row['GEOMETRY']) else
        spl.LineString([[row['coordinateX'], row['coordinateY']], [row['coordinateX3'], row['coordinateY3']]])), axis=1
                              )
    df['polygon'] = spl.to_geojson(contour)

    df['oilfield'] = df['oilfield'].str.upper()

    # Переименование колонок
    df = df[dict_rename.keys()]
    df.columns = dict_rename.values()
    df['Дата'] = pd.to_datetime(df['Дата'])
    return df


@logger.catch(level='DEBUG')
def save_report_to_db(db_result, dict_result, dict_parameters, list_name_params):
    """
    Сохраняет отчетные данные и параметры расчета в базу данных.

    :param db_result: sqlite3.Connection - подключение к базе данных
    :param dict_result: dict - результаты расчетов
    :param dict_parameters: dict - параметры расчета
    :param list_name_params: list - список имен параметров
    """
    logger.info('Запись отчетной таблицы в базу данных')
    df_report = get_report(dict_result)
    df_report.to_sql(name='report', con=db_result, if_exists='replace')

    # Параметры расчета
    logger.info('Запись параметров расчета в базу данных')
    df_params = pd.DataFrame([{new_key: ', '.join(map(str, dict_parameters[old_key]))
    if isinstance(dict_parameters[old_key], list) else str(dict_parameters[old_key])
                               for new_key, old_key in zip(list_name_params, dict_parameters.keys())}])
    df_params.to_sql(name='parameters', con=db_result, if_exists='replace')
