import numpy as np
import pandas as pd
from loguru import logger
from tqdm import tqdm

from FirstRowWells import mean_radius
from geometry import add_shapely_types, check_intersection_area


def dict_mesh_keys(list_coef, contour_name):
    """
    Создание словаря для записи результатов построения результатов регулярной сетки
    :param list_coef: список коэффициентов кратного увеличения радиуса
    :param contour_name: имя контура, по которому идет расчет
    :return: сформированный пустой словарь с требуемыми ключами
    """
    list_keys = [f'{contour_name}, k = {x}' for x in list_coef]
    dict_result = dict.fromkeys(list_keys, pd.DataFrame())
    return dict_result


def calc_regular_mesh(df, dict_parameters, contour_name):
    """
    Построение регулярной сети для каждого типа скважин
    :param df: DataFrame после предварительной обработки, сформированный из выгрузки данных по скважинам
    :param dict_parameters: словарь с параметрами расчета
    :param contour_name: имя контура, по которому идет расчет
    :return: словарь, содержащий по ключу DataFrame с регулярной сеткой из скважин
    """
    list_horizon = list(set(df.workHorizon.str.replace(" ", "").str.split(",").explode()))
    list_horizon.sort()
    dict_result = dict_mesh_keys(dict_parameters['mult_coef'], contour_name)
    for horizon in tqdm(list_horizon, "Calculation regular mesh", position=0, leave=True,
                        colour='white', ncols=80):
        df_horizon_input = df[
            list(map(lambda x: len(set(x.replace(" ", "").split(",")) & set([horizon])) > 0, df.workHorizon))]
        mean_rad, df_horizon_input = mean_radius(df_horizon_input, dict_parameters['verticalWellAngle'],
                                                 dict_parameters['MaxOverlapPercent'],
                                                 dict_parameters['angle_horizontalT1'],
                                                 dict_parameters['angle_horizontalT3'], dict_parameters['max_distance'])
        df_horizon_input['current_horizon'] = horizon
        for key, coeff in zip(dict_result, dict_parameters['mult_coef']):
            logger.info(f'Add shapely types with coefficient = {coeff}')
            df_result = fond_mesh(df_horizon_input, dict_parameters, mean_rad, coeff)
            df_result = add_shapely_types(df_result, mean_rad, coeff)
            dict_result[key] = pd.concat([dict_result[key], df_result], axis=0, sort=False).reset_index(drop=True)
    return dict_result


def fond_mesh(df_horizon, dict_parameters, mean_rad, coeff):
    """
    Построение регулярной сети по выбранному фонду
    :param dict_parameters:
    :param df_horizon: DataFrame скважин, выделенных на определенный объект работы
    :param mean_rad: средний радиус по текущему объекту
    :param coeff: коэффициент кратного увеличения радиуса
    :return: результирующий DataFrame с регулярной сеткой по текущему фонду скважин
    """
    df_result = pd.DataFrame()
    list_fonds = list(set(df_horizon['fond'].explode().unique()))
    list_fonds.sort()
    df_horizon = add_shapely_types(df_horizon, mean_rad, coeff)
    df_fond_mesh = df_horizon.copy()
    # проходимся по каждому фонду (добывающий, нагнетательный, пьезометрический)
    for fond in tqdm(list_fonds, "Calculation clusters for fond", position=0, leave=True,
                     colour='white', ncols=80):
        # выделение DataFrame на фонд (добывающий, нагнетательный, пьезометрический)
        df_fond = df_fond_mesh[df_fond_mesh['fond'] == fond]
        list_geometry = df_fond['GEOMETRY'].to_list()
        list_distances = []
        while len(list_geometry) != 1:
            current = list_geometry[0]
            list_geometry = [x for x in list_geometry if x != current]
            for geo in list_geometry:
                list_distances += [current.distance(geo)]

        list_check_well = []
        if df_fond.shape[0] > 1:
            df_fond['intersection'] = list(
                map(lambda x, y: check_intersection_area(x, df_fond[df_fond.wellName != y],
                                                         dict_parameters['single_percent'], True),
                    df_fond.AREA, df_fond.wellName))
            df_fond['number'] = df_fond['intersection'].apply(lambda x: np.size(x))
            df_fond = df_fond.sort_values(by=['number'], axis=0, ascending=False)
            list_optim = list(df_fond['wellName'].explode())
            while len(list_optim) != 0:
                list_check_well += [list_optim[0]]
                list_exception = [list_optim[0]] + list(
                    df_fond[df_fond['wellName'] == list_optim[0]][
                        'intersection'].explode().unique())
                list_optim = [x for x in list_optim if x not in list_exception]
        else:
            list_check_well += [df_fond['wellName'].iloc[0]]
        df_current_result = df_fond[df_fond['wellName'].isin(list_check_well)]
        # df_current_result['count_basic_wells'] = df_current_result.shape[0]
        # df_current_result['count_of_search'] = (df_fond_mesh[df_fond_mesh['fond'] == fond].shape[0]
        #                                         - df_current_result.shape[0])
        # df_current_result['specific_area'] = (unary_union(list(df_current_result['AREA'].explode())).area
        #                                       / df_current_result.shape[0])

        df_result = pd.concat([df_result, df_current_result], axis=0, sort=False).reset_index(drop=True)

    return df_result
