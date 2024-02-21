import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from loguru import logger
from scipy.cluster.hierarchy import fcluster, average
from shapely.geometry import LineString
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
        # horizon = 'НП4'
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
            df_result = df_result[['wellName', 'nameDate', 'workMarker', 'wellStatus',
                                   'oilfield', 'workHorizon', 'wellCluster', 'coordinateX',
                                   'coordinateY', 'coordinateX3', 'coordinateY3', 'fond',
                                   'gasStatus', 'POINT', 'POINT3', 'GEOMETRY', 'min_dist',
                                   'AREA', 'current_horizon']]
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
        array_dist = np.array(list_distances)
        df_fond = clustering_well(df_fond, mean_rad, coeff, array_dist)
        df_separation = separate_wells(df_fond.copy(), 7)
        #  формируем список кластеров, которые есть в текущем фонде
        list_cluster = list(set(df_fond['cluster'].explode().unique()))
        # mapping_cluster(df_fond, 'НП2-3')

        list_check_well = []
        if df_fond.shape[0] > 1:
            df_fond['intersection'] = list(
                map(lambda x, y: check_intersection_area(x, df_fond[df_fond.wellName != y],
                                                         dict_parameters['percent'], True),
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
        #  проход по всем кластерам фонда с целью посчитать координаты центроида кластера
        # for cluster in list_cluster:
        #     df_current_cluster = df_fond[df_fond['cluster'] == cluster]
        #
        #     # ----------OPTIMIZATION------------
        #
        #     if df_current_cluster.shape[0] > 1:
        #         df_current_cluster['intersection'] = list(
        #             map(lambda x, y: check_intersection_area(x, df_current_cluster[df_current_cluster.wellName != y],
        #                                                      dict_parameters['percent'], True),
        #                 df_current_cluster.AREA, df_current_cluster.wellName))
        #         df_current_cluster['number'] = df_current_cluster['intersection'].apply(lambda x: np.size(x))
        #         df_current_cluster = df_current_cluster.sort_values(by=['number'], axis=0, ascending=False)
        #         list_optim = list(df_current_cluster['wellName'].explode())
        #         while len(list_optim) != 0:
        #             list_check_well += [list_optim[0]]
        #             list_exception = [list_optim[0]] + list(
        #                 df_current_cluster[df_current_cluster['wellName'] == list_optim[0]][
        #                     'intersection'].explode().unique())
        #             list_optim = [x for x in list_optim if x not in list_exception]
        #     else:
        #         list_check_well += [df_current_cluster['wellName'].iloc[0]]

        # ----------OPTIMIZATION------------
        # df_minor = df_fond[~df_fond['wellName'].isin(list_check_well)]
        # df_basic = df_fond[df_fond['wellName'].isin(list_check_well)]
        # if not df_minor.empty:
        #     df_minor['intersection'] = list(
        #         map(lambda x: check_intersection_point(x, df_basic, dict_parameters['percent'], True),
        #             df_minor.GEOMETRY))
        #     df_minor = df_minor[df_minor['intersection'].map(lambda x: np.size(x) == 0)]
        #     df_minor['intersection'] = list(
        #         map(lambda x, y: check_intersection_area(x, df_minor[df_minor.wellName != y],
        #                                                  dict_parameters['percent'], True),
        #             df_minor.AREA, df_minor.wellName))
        #     df_minor['number'] = df_minor['intersection'].apply(lambda x: np.size(x))
        #     df_minor = df_minor.sort_values(by=['number'], axis=0, ascending=False)
        #     list_optim = list(df_minor['wellName'].explode())
        #     list_check_wells = []
        #     while len(list_optim) != 0:
        #         list_check_wells += [list_optim[0]]
        #         list_exception = [list_optim[0]] + list(
        #             df_minor[df_minor['wellName'] == list_optim[0]]['intersection'].explode().unique())
        #         list_optim = [x for x in list_optim if x not in list_exception]
        #     df_basic['intersection'] = list(
        #         map(lambda x: check_intersection_point(x, df_minor[df_minor['wellName'].isin(list_check_wells)],
        #                                                dict_parameters['percent'], True),
        #             df_basic.GEOMETRY))
        #     list_exception_basic = list(
        #         df_basic[df_basic['intersection'].map(lambda x: np.size(x) > 0)].wellName.explode().unique())
        #     list_centroid_well = [x for x in list_centroid_well if x not in list_exception_basic]
        #     list_centroid_well += list_check_wells
        df_result = pd.concat([df_result, df_fond[df_fond['wellName'].isin(list_check_well)]],
                              axis=0, sort=False).reset_index(drop=True)

    return df_result


def optim_geometry(welltype, point, point3):
    """

    :param welltype:
    :param point:
    :param point3:
    :return:
    """
    geom = point
    if welltype == 'horizontal':
        geom = LineString(tuple(point.coords) + tuple(point3.coords))

    return geom


def separate_wells(df_input, count_of_segments):
    """
    Разбитие траектории ГС на точки, отстоящие друг от друга на 50 метров
    :param count_of_segments: кол-во отрезков разбиения ГС
    :param df_input: DataFrame скважин, выделенных на один определенный объект работы
    :return: возвращает DataFrame c добавленными строками для ГС (кол-во строк равно кол-ву точек разбиения ГС)
    """
    logger.info(f'Separate horizontal wells by points through the length')
    list_hor_hells = list(df_input[df_input['well type'] == 'horizontal'].wellName.explode().unique())

    for well in list_hor_hells:
        geom = df_input[df_input['wellName'] == well]['GEOMETRY'].values[0]
        df_well_divide = df_input[df_input['wellName'] == well]
        df_input = df_input.loc[df_input['wellName'] != well]
        divide_geometry_list = geom.interpolate(np.linspace(0, 1, int(count_of_segments)), normalized=True).tolist()

        for point in divide_geometry_list:
            df_well_divide['GEOMETRY'] = df_well_divide['GEOMETRY'].apply(lambda x: [point.x, point.y])
            df_input = pd.concat([df_input, df_well_divide], axis=0, sort=False).reset_index(drop=True)

    df_input['GEOMETRY'] = df_input.apply(lambda a:
                                          [a['GEOMETRY'].x, a['GEOMETRY'].y]
                                          if a['well type'] == 'vertical' else a['GEOMETRY'], axis=1)
    return df_input


def clustering_well(df_test, mean_rad, coeff, array_dist):
    """

    :param array_dist:
    :param coeff: коэффициент кратного увеличения радиуса исследования
    :param mean_rad: средний радиус исследования по объекту
    :param df_test: DataFrame, в котором необходимо провести дробление ГС
    :return:
    """
    logger.info(f'Try search clusters with radius {mean_rad}')
    try:
        list_clusters = fcluster(average(array_dist), t=coeff * mean_rad, criterion='distance').tolist()
        df_test['cluster'] = pd.Series(list_clusters).values
    except ValueError:
        df_test['cluster'] = 1

    return df_test


def mapping_cluster(df_cluster, horizon):
    """

    :param df_cluster:
    :param horizon:
    :return:
    """
    from random import randint

    dict_colors = dict.fromkeys(df_cluster['cluster'].explode().unique())
    color = []
    n = 3
    for key in dict_colors.keys():
        dict_colors[key] = '#%06X' % randint(0, 0xFFFFFF)

    fig, ax = plt.subplots()
    for k, d in df_cluster.groupby('cluster'):
        gpd.GeoSeries(d['GEOMETRY']).plot(ax=ax, color=dict_colors[d['cluster'].iloc[0]])
    # !!!ДЛЯ РАЗБИТЫХ НА ТОЧКИ ГС!!!
    # fig, ax = plt.subplots()
    # for k, d in df_cluster.groupby('cluster'):
    #     d = pd.DataFrame(d['GEOMETRY'].to_list(), columns=['X', 'Y'])
    #     ax.scatter(d['X'], d['Y'], label=k)
    plt.legend(loc='center left', bbox_to_anchor=(1, 0.5))
    plt.savefig(f'output/{horizon} clusters.png')
    plt.show()
    pass
