import numpy as np
import pandas as pd
from loguru import logger
from shapely.ops import unary_union
from tqdm import tqdm

from FirstRowWells import mean_radius
from geometry import add_shapely_types, check_intersection_area
from wells_clustering import dict_mesh_keys


def calc_mesh_by_holes(df_input, dict_parameters, contour_name):
    """
    Расчет регулярной сетки для каждого объекта/радиуса исследования/фонда
    :param df_input: DataFrame исходных данных по скважинам
    :param dict_parameters: словарь с параметрами расчета
    :param contour_name: имя контура, по которому идет расчет
    :return: словарь с названиями ключей в виде сценариев расчета и готовыми DataFrame c опорными скважинами
    """
    list_horizon = list(set(df_input.workHorizon.str.replace(" ", "").str.split(",").explode()))
    list_horizon.sort()
    # словарь для записи результатов
    dict_holes_result = dict_mesh_keys(dict_parameters['mult_coef'], contour_name)
    for horizon in tqdm(list_horizon, "Calculation mesh by holes", position=0, leave=True,
                        colour='white', ncols=80):
        logger.info(f'Current horizon: {horizon}')
        # отбираю скважины на объект
        df_horizon = df_input[
            list(map(lambda x: len(set(x.replace(" ", "").split(",")) & set([horizon])) > 0, df_input.workHorizon))]
        mean_rad, df_horizon = mean_radius(df_horizon, dict_parameters['verticalWellAngle'],
                                           dict_parameters['MaxOverlapPercent'],
                                           dict_parameters['angle_horizontalT1'],
                                           dict_parameters['angle_horizontalT3'], dict_parameters['max_distance'])
        df_horizon['current_horizon'] = horizon
        for key, coeff in zip(dict_holes_result, dict_parameters['mult_coef']):
            logger.info(f'Calculate by key {key} with coefficient {coeff}')
            df_horizon = add_shapely_types(df_horizon, mean_rad, coeff)
            df_result = holes_calc_fond(df_horizon, dict_parameters, mean_rad, coeff)
            dict_holes_result[key] = pd.concat([dict_holes_result[key], df_result], axis=0, sort=False).reset_index(
                drop=True)
    return dict_holes_result


def holes_calc_fond(df_horizon, dict_parameters, mean_rad, coeff):
    """
    Расчет регулярной сети по обекту месторождения
    :param df_horizon: DataFrame скважин, выделенный из исходных данных на текущий объект работы
    :param dict_parameters: словарь с параметрами расчета
    :param mean_rad: средний радиус по объекту расчета
    :param coeff: коэффициент кратного увеличения радиуса исследования
    :return: объединенный по фондам объекта DataFrame с регулярной сеткой скважин
    """
    df_result = pd.DataFrame()
    list_fonds = list(set(df_horizon['fond'].explode().unique()))
    list_fonds.sort()

    for fond in tqdm(list_fonds, "Holes algorithm for fond", position=0, leave=True,
                     colour='white', ncols=80):
        # выделение скважин для текущего фонда итерации
        df_fond_main = df_horizon[df_horizon['fond'] == fond]
        df_fond_main['R'] = add_shapely_types(df_fond_main, mean_rad, coeff)['AREA']
        df_fond_main['2R'] = add_shapely_types(df_fond_main, 2 * mean_rad, coeff)['AREA']
        df_fond_main['3R'] = add_shapely_types(df_fond_main, 3 * mean_rad, coeff)['AREA']
        df_fond = df_fond_main.copy()

        list_fond_wells = list(df_fond['wellName'].explode().unique())
        length_list_wells = len(list_fond_wells)
        list_basic_wells = []
        for i in range(length_list_wells):
            if len(list_fond_wells) == 0:
                break
            # выбор первой опорной скважины из DataFrame
            df_first_well = find_first_well(df_fond)
            # поиск охваченных скважин
            df_first_well['intersection'] = list(
                map(lambda x, y: check_intersection_area(x, df_fond[df_fond['wellName'] != y],
                                                         dict_parameters['single_percent'], True),
                    df_first_well['R'], df_first_well['wellName']))
            # список охваченных скважин в пределах расстояния 1*R
            list_R = list(set(df_first_well['intersection'].iloc[0]))
            list_basic_wells += [df_first_well['wellName'].iloc[0]]
            df_first_well['intersection_2r'] = list(
                map(lambda x, y: check_intersection_area(x, df_fond[df_fond['wellName'] != y],
                                                         dict_parameters['single_percent'], True),
                    df_first_well['2R'], df_first_well['wellName']))
            list_2R = list(
                set(df_first_well['intersection_2r'].iloc[0]) - set(df_first_well['intersection'].iloc[0]))
            # проверка на охват выбранной скважины скважинами второго ряда
            if list_2R:
                # DataFrame из скважин второй зоны
                df_2R = df_fond[df_fond['wellName'].isin(list_2R)]
                # поиск скважин из второй зоны, которые охватывают с заданным радиусом выбранную
                df_2R['intersection_first'] = list(
                    map(lambda x: check_intersection_area(x, df_fond_main[
                        df_fond_main['wellName'].isin([list_basic_wells[-1]])],
                                                          dict_parameters['single_percent'], True), df_2R['R']))
                # кол-во пересечений, но тк в функцию подается только одна скважина для проверки ее охвата, максимальное
                # число пересечений равно 1
                df_2R['count_intersect'] = df_2R['intersection_first'].apply(lambda x: np.size(x))
                # список скважин, охватывающих текущую выбранную, из них далее берется первая и на нее переносится метка
                list_replace_marker = list(df_2R.loc[df_2R['count_intersect'] > 0].wellName.explode())
                if list_replace_marker:
                    list_basic_wells += [list_replace_marker[0]]
                    list_basic_wells = [x for x in list_basic_wells if x != df_first_well['wellName'].iloc[0]]
                    df_first_well = df_fond_main.loc[df_fond_main['wellName'] == list_replace_marker[0]]
                    df_first_well['intersection'] = list(
                        map(lambda x, y: check_intersection_area(x, df_fond[df_fond['wellName'] != y],
                                                                 dict_parameters['single_percent'], True),
                            df_first_well['R'], df_first_well['wellName']))
                    # список охваченных скважин в пределах расстояния 1*R
                    list_R = list(set(df_first_well['intersection'].iloc[0]))
                    df_first_well['intersection_2r'] = list(
                        map(lambda x, y: check_intersection_area(x, df_fond[df_fond['wellName'] != y],
                                                                 dict_parameters['single_percent'], True),
                            df_first_well['2R'], df_first_well['wellName']))
                    list_2R = list(
                        set(df_first_well['intersection_2r'].iloc[0]) - set(df_first_well['intersection'].iloc[0]))

            list_fond_wells = [x for x in list_fond_wells if x not in list_R + [df_first_well['wellName'].iloc[0]]]
            df_fond = df_fond[df_fond['wellName'].isin(list_fond_wells)]
            df_first_well['intersection_3r'] = list(
                map(lambda x, y: check_intersection_area(x, df_fond[df_fond['wellName'] != y],
                                                         dict_parameters['single_percent'], True),
                    df_first_well['3R'], df_first_well['wellName']))
            list_3R = list(
                set(df_first_well['intersection_3r'].iloc[0]) - set(df_first_well['intersection_2r'].iloc[0]))
            df_3R = df_fond[df_fond['wellName'].isin(list_3R)]
            # идет расчет по зоне 3R, причем изначально рассматриваются скважины, расположенные ближе к полигону 2R
            if not df_3R.empty:
                df_3R['distance'] = df_3R.apply(lambda x: x['GEOMETRY'].distance(df_first_well['2R'].iloc[0]), axis=1)
                df_3R = df_3R.sort_values(by=['distance'], axis=0, ascending=True)
                # в процессе расчета удаляются охваченные скважины из list_2R
                df_3R['intersection'] = list(
                    map(lambda x, y: check_intersection_area(x, df_fond[df_fond['wellName'] != y],
                                                             dict_parameters['single_percent'], True), df_3R['R'],
                        df_3R['wellName']))
                list_3R = list(df_3R['wellName'].explode())
                while not df_3R.empty:
                    current_well = list_3R[0]
                    list_exception = list(set(df_3R[df_3R['wellName'] == current_well]['intersection'].iloc[0])) + [
                        current_well]
                    list_fond_wells = [x for x in list_fond_wells if x not in list_exception]
                    list_3R = [x for x in list_3R if x not in list_exception]
                    list_2R = [x for x in list_2R if x not in list_exception]

                    list_basic_wells += [current_well]
                    df_3R = df_3R[df_3R['wellName'].isin(list_3R)]
            # переопределение DataFrame на фонд
            df_fond = df_fond[df_fond['wellName'].isin(list_fond_wells)]
            # создается DataFrame из фонда, содержащий скважины из list_2R. Если list_2R пустой, то есть условие
            df_2R = df_fond[df_fond['wellName'].isin(list_2R)]
            if not df_2R.empty:
                df_2R['distance'] = df_2R.apply(
                    lambda x: x['GEOMETRY'].distance(df_first_well['2R'].iloc[0].boundary), axis=1)
                df_2R = df_2R.sort_values(by=['distance'], axis=0, ascending=True)
                df_2R['intersection'] = list(
                    map(lambda x, y: check_intersection_area(x, df_fond[df_fond['wellName'] != y],
                                                             dict_parameters['single_percent'], True), df_2R['R'],
                        df_2R['wellName']))
                list_2R = list(df_2R['wellName'].explode())
                while not df_2R.empty:
                    current_well = list_2R[0]
                    list_exception = list(set(df_2R[df_2R['wellName'] == current_well]['intersection'].iloc[0])) + [
                        current_well]
                    list_fond_wells = [x for x in list_fond_wells if x not in list_exception]
                    list_2R = [x for x in list_2R if x not in list_exception]
                    list_basic_wells += [current_well]
                    df_2R = df_2R[df_2R['wellName'].isin(list_2R)]
                    # переопределение DataFrame на фонд
                df_fond = df_fond[df_fond['wellName'].isin(list_fond_wells)]
        df_current_result = df_horizon[df_horizon['wellName'].isin(list_basic_wells)]
        df_current_result['intersection'], df_current_result['number'] = 0, 0
        df_current_result['count_basic_wells'] = df_current_result.shape[0]
        df_current_result['count_of_search'] = df_fond_main.shape[0] - df_current_result.shape[0]
        df_current_result['specific_area'] = (unary_union(list(df_current_result['AREA'].explode())).area
                                              / df_current_result.shape[0])

        df_result = pd.concat([df_result, df_current_result], axis=0,
                              sort=False).reset_index(drop=True)
    return df_result


def find_first_well(df):
    """
    Поиск основной скважины по минимальной кооринате Y для начала итерации
    :param df: DataFrame с данными по одному из фондов выделенный из исходного
    :return: строчку DataFrame с данными по выбранной скважине
    """
    min_y = df[['coordinateY', 'coordinateY3']].values.min()
    if df[(df['coordinateY'] == min_y) | (df['coordinateY3'] == min_y)].shape[0] != 1:
        df = df[(df['coordinateY'] == min_y) | (df['coordinateY3'] == min_y)]
        min_x = df[['coordinateX', 'coordinateX3']].values.min()
        df = df[(df['coordinateX'] == min_x) | (df['coordinateX3'] == min_x)]
        first_well = df[df['wellName'] == df['wellName'].iloc[0]]
        return first_well
    else:
        first_well = df[(df['coordinateY'] == min_y) | (df['coordinateY3'] == min_y)]
        return first_well
