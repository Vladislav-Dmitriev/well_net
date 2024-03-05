import numpy as np
import pandas as pd
from shapely.ops import cascaded_union
from shapely.ops import unary_union
from tqdm import tqdm

from functions import get_property, get_time_coef
from geometry import check_intersection_area


def calc_regular_mesh(df_prod_wells, df_piez_wells, df_inj_wells, df_result, horizon,
                      path_property, dict_parameters, obj_square, mean_rad, coeff):
    """
    Расчет регулярной сетки скважин
    :param df_prod_wells: DataFrame добывающих скважин на текущий объект расчета
    :param df_piez_wells: DataFrame пьезометрических скважин на текущий объект расчета
    :param df_inj_wells: DataFrame нагнетательных скважин на текущий объект расчета
    :param df_result: результирующий DataFrame содержащий опорные скважины
    :param horizon: текущий объект расчета
    :param path_property: путь к файлу с PVT свойствами
    :param dict_parameters: словарь с параметрами расчета
    :param obj_square: площадь текущего объекта расчетп по крайним скважиам
    :param mean_rad: средний радиус исследования по текущему объекта
    :param coeff: коэффициент кратного увеличения радиуса исследования
    :return: результирующий DataFrame с опорными скважинами
    """
    inj_count = df_inj_wells.shape[0]
    prod_count = df_prod_wells.shape[0]
    piez_count = df_piez_wells.shape[0]
    dict_fonds = {}
    dict_fonds['ПЬЕЗ'] = df_piez_wells
    dict_fonds['НАГ'] = df_inj_wells
    dict_fonds['ДОБ'] = df_prod_wells
    # площадь охваченная после выбора опорных скважин
    current_area = 0
    list_polygons = []
    # проходимся по каждому фонду (добывающий, нагнетательный, пьезометрический)
    for fond in tqdm(dict_parameters['list_order_fond'], "Regular mesh for fond", position=0, leave=True,
                     colour='white', ncols=80):
        # выделение DataFrame на фонд (добывающий, нагнетательный, пьезометрический)
        df_fond = dict_fonds[fond]
        if df_fond.empty:
            continue
        # условие на очистку DataFrame, если до текущей итерации уже были отобраны опорные скважины из другого фонда
        # и охватили какую-то площадь

        if current_area != 0:
            df_fond = df_fond[~df_fond['wellName'].isin(check_intersection_area(current_area, df_fond,
                                                                                dict_parameters['percent'],
                                                                                dict_parameters['calc_option']))]

        list_check_well = []
        if df_fond.shape[0] > 0:
            df_fond['intersection'] = list(
                map(lambda x, y: check_intersection_area(x, df_fond[df_fond.wellName != y],
                                                         dict_parameters['percent'],
                                                         dict_parameters['calc_option']),
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
            continue

        df_current_result = df_fond[df_fond['wellName'].isin(list_check_well)]

        if current_area == 0:
            list_polygons = list(df_current_result['AREA'].explode())
            current_area = cascaded_union(list_polygons)
        else:
            list_polygons = list_polygons + list(df_current_result['AREA'].explode())
            current_area = cascaded_union(list_polygons)

        # ax = gpd.GeoSeries(current_area).plot(color="springgreen", figsize=[20, 20])
        # gpd.GeoSeries(current_area).boundary.plot(ax=ax, color='green')
        # df_current_result = df_current_result.set_geometry('GEOMETRY')
        # df_current_result.plot(ax=ax, color='black', markersize=14, marker='^')
        # for x, y, label in zip(df_current_result.coordinateX.values,
        #                        df_current_result.coordinateY.values,
        #                        df_current_result.wellName):
        #     ax.annotate(label, xy=(x, y), xytext=(3, 3), textcoords="offset points", color="navy",
        #                 fontsize=6)
        # plt.savefig(f'output/MESH_test_{fond}.png', dpi=200)
        # plt.clf()

        df_current_result[
            'mean_radius'] = mean_rad * coeff  # столбец с текущим средним радиусом по объекту, домножается на коэфф.
        df_current_result['min_dist'] = df_current_result['min_dist'] * coeff
        # расчет времени исследования с использованием PVT справочника
        dict_property = get_property(path_property)
        df_current_result['time_coef/objects'] = df_current_result.apply(
            lambda x: get_time_coef(dict_property, x.workHorizon, x.water_cut, x.oilfield, x.gasStatus), axis=1)
        df_current_result['time_coef'] = list(map(lambda x: x[0], df_current_result['time_coef/objects']))
        # df_result['mu'] = list(map(lambda x: x[1], df_result['time_coef/objects']))
        # df_result['ct'] = list(map(lambda x: x[2], df_result['time_coef/objects']))
        # df_result['phi'] = list(map(lambda x: x[3], df_result['time_coef/objects']))
        df_current_result['k'] = list(map(lambda x: x[4], df_current_result['time_coef/objects']))  # проницаемость
        df_current_result['gas_visc'] = list(
            map(lambda x: x[5], df_current_result['time_coef/objects']))  # вязкость газа в пл. условиях
        df_current_result['pressure'] = list(
            map(lambda x: x[6], df_current_result['time_coef/objects']))  # пл. давление кгс/см2
        df_current_result['default_count'] = list(
            map(lambda x: x[7], df_current_result['time_coef/objects']))  # кол-во объектов
        # со свойствами по умолчанию
        df_current_result['obj_count'] = list(map(lambda x: x[8], df_current_result['time_coef/objects']))
        df_current_result['percent_of_default'] = list(
            map(lambda x: 100 * x[5] / x[6], df_current_result['time_coef/objects']))  # процент
        # объектов со свойствами по умолчанию
        df_current_result.drop(['time_coef/objects'], axis=1, inplace=True)
        df_current_result[
            'current_horizon'] = horizon  # добавления столбца объектов для понимания, по какому идет расчет
        df_current_result['research_time'] = (df_current_result['min_dist'] * df_current_result['min_dist']
                                              * df_current_result[
                                                  'time_coef'])  # время исследования в сут через min расстояние
        df_current_result['oil_loss'] = 0
        df_current_result['gas_loss'] = 0
        df_current_result['injection_loss'] = 0
        df_current_result['oil_loss'] = df_current_result.apply(
            lambda x: (x.oilRate + x.condRate) * x.research_time if (
                    str(x.gasStatus) == 'газоконденсатная') else x.oilRate * x.research_time, axis=1)  # потери по нефти
        df_current_result['gas_loss'] = df_current_result.apply(lambda x: (x.injectivity_day * x.research_time) if (
                str(x.gasStatus) == 'газонагнетательная') else x.gasRate * x.research_time, axis=1)  # потери по газу
        df_current_result['injection_loss'] = df_current_result['injectivity'] * df_current_result[
            'research_time']  # потери по закачке воды
        df_current_result['coverage_percentage'] = unary_union(
            list(df_current_result['AREA'].explode())).area / obj_square
        # процент скважин в опорной сети из скважин на объекте по каждому типу
        df_current_result['percent_piez_wells'] = 0
        if df_piez_wells.shape[0] != 0:
            df_current_result['percent_piez_wells'] = df_current_result[df_current_result['fond'] == 'ПЬЕЗ'].shape[
                                                          0] / piez_count
        df_current_result['percent_inj_wells'] = 0
        if df_inj_wells.shape[0] != 0:
            df_current_result['percent_inj_wells'] = df_current_result[df_current_result['fond'] == 'НАГ'].shape[
                                                         0] / inj_count
        df_current_result['percent_prod_wells'] = 0
        if df_prod_wells.shape[0] != 0:
            df_current_result['percent_prod_wells'] = df_current_result[df_current_result['fond'] == 'ДОБ'].shape[
                                                          0] / prod_count
        df_current_result['year_of_survey'] = 0

        df_result = pd.concat([df_result, df_current_result], axis=0, sort=False).reset_index(drop=True)

    return df_result
