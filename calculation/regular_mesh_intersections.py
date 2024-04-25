import math

import numpy as np
import pandas as pd
from shapely.ops import cascaded_union
from shapely.ops import unary_union
from tqdm import tqdm

from calculation.auxiliary_functions import get_property, get_time_coef
from calculation.geometry import check_intersection_area


def calc_regular_mesh(df_prod_wells, df_piez_wells, df_inj_wells, df_proj_wells, df_result, df_necessarily_wells,
                      horizon, path_property, dict_parameters, obj_square, mean_rad, coeff, list_exception):
    """
    Расчет регулярной сетки скважин
    :param list_exception: список скважин для исключения из ОС
    :param df_necessarily_wells: DataFrame скважин, обязательных для включения в ОС
    :param df_proj_wells: DataFrame проектных скважин
    :param df_prod_wells: DataFrame добывающих скважин на текущий объект расчета
    :param df_piez_wells: DataFrame пьезометрических скважин на текущий объект расчета
    :param df_inj_wells: DataFrame нагнетательных скважин на текущий объект расчета
    :param df_result: результирующий DataFrame содержащий опорные скважины
    :param horizon: текущий объект расчета
    :param path_property: путь к файлу с PVT свойствами
    :param dict_parameters: словарь с параметрами расчета
    :param obj_square: площадь текущего объекта расчета по крайним скважинам
    :param mean_rad: средний радиус исследования по текущему объекта
    :param coeff: коэффициент кратного увеличения радиуса исследования
    :return: результирующий DataFrame с опорными скважинами
    """
    # удаление исключенных скважин из DataFrame пьезометров, нагнетательных и добывающих
    df_piez_wells = df_piez_wells[~df_piez_wells['wellName'].isin(list_exception)]
    df_inj_wells = df_inj_wells[~df_inj_wells['wellName'].isin(list_exception)]
    df_prod_wells = df_prod_wells[~df_prod_wells['wellName'].isin(list_exception)]
    # кол-во скважин в каждом фонде для определения процента вхождения в ОС
    inj_count = df_inj_wells.shape[0] + df_necessarily_wells[df_necessarily_wells['fond'] == 'НАГ'].shape[0]
    prod_count = df_prod_wells.shape[0] + df_necessarily_wells[df_necessarily_wells['fond'] == 'ДОБ'].shape[0]
    piez_count = df_piez_wells.shape[0] + df_necessarily_wells[df_necessarily_wells['fond'] == 'ПЬЕЗ'].shape[0]
    gas_prod_count = df_prod_wells[df_prod_wells['gasStatus'].str.contains('газ')].shape[0] + df_necessarily_wells[
        (df_necessarily_wells['fond'] == 'ДОБ') & (df_necessarily_wells['gasStatus'].str.contains('газ'))].shape[0]
    # словарь с DataFrame каждого фонда, процентом скважин в ОС и приоритетных скважин
    dict_fonds = {}
    dict_fonds['ПЬЕЗ'] = [df_piez_wells, dict_parameters['percent_piez'],
                          df_necessarily_wells[df_necessarily_wells['fond'] == 'ПЬЕЗ']]
    dict_fonds['НАГ'] = [df_inj_wells, dict_parameters['percent_inj'],
                         df_necessarily_wells[df_necessarily_wells['fond'] == 'НАГ']]
    dict_fonds['ДОБ'] = [df_prod_wells, dict_parameters['percent_prod'],
                         df_necessarily_wells[df_necessarily_wells['fond'] == 'ДОБ']]
    # площадь охваченная после выбора опорных скважин
    current_area = 0
    list_polygons = []
    df_current_result = pd.DataFrame()
    # проходимся по каждому фонду (добывающий, нагнетательный, пьезометрический)
    for fond in tqdm(dict_parameters['list_order_fond'], "Regular mesh for fond", position=0, leave=True,
                     colour='white', ncols=80):
        # выделение DataFrame на фонд (добывающий, нагнетательный, пьезометрический) и процента скважин в ОС от фонда
        df_fond = dict_fonds[fond][0]
        wellnet_percent = dict_fonds[fond][1]
        df_necessarily_fond = dict_fonds[fond][2]

        if df_fond.empty and df_necessarily_fond.empty:
            continue

        # условие на очистку DataFrame, если до текущей итерации уже были отобраны опорные скважины из другого фонда
        # и охватили какую-то площадь
        if current_area != 0 and not df_fond.empty:
            df_fond = df_fond[~df_fond['wellName'].isin(list(check_intersection_area(current_area, df_fond,
                                                                                     dict_parameters['percent'],
                                                                                     dict_parameters['calc_option'])))]

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
                if (len(df_fond['intersection'].explode().unique()) == 1) and (
                        math.isnan(df_fond['intersection'].explode().unique()[0])):
                    list_check_well = list_optim.copy()
                    break
                list_check_well += [list_optim[0]]
                list_exception = [list_optim[0]] + list(
                    df_fond[df_fond['wellName'] == list_optim[0]][
                        'intersection'].explode().unique())
                list_optim = [x for x in list_optim if x not in list_exception]
            # добавление обязательных скважин r результирующему DataFrame
            df_current_result = df_fond[df_fond['wellName'].isin(list_check_well)]
            df_current_result = pd.concat([df_necessarily_fond, df_current_result], axis=0, sort=False).reset_index(
                drop=True)
        elif df_fond.empty and not df_necessarily_fond.empty:
            df_current_result = pd.concat([df_necessarily_fond, df_current_result], axis=0, sort=False).reset_index(
                drop=True)
        else:
            continue

        # функция проверки процента скважин в опорной сети от текущего фонда
        count_target = math.ceil(wellnet_percent / 100 * (df_fond.shape[0] + df_necessarily_fond.shape[0]))
        if df_current_result.shape[0] > count_target:
            df_current_result = df_current_result.sort_values(by=['number'], axis=0, ascending=False)
            list_out_wellnet = df_current_result[
                               -(df_current_result.shape[0] - count_target):].wellName.explode().unique()
            df_current_result.loc[
                df_current_result['wellName'].isin(list_out_wellnet), 'intersection'] = 'Исключена из ОС'
        # добавить недостающие скважины в ОС
        elif df_current_result.shape[0] < count_target:
            df_fond = df_fond[~df_fond['wellName'].isin(list(df_current_result['wellName'].explode().unique()))]
            df_fond = df_fond.sort_values(by=['number'], axis=0, ascending=True)
            df_fond = df_fond[:(count_target - df_current_result.shape[0])]
            df_current_result = pd.concat([df_current_result, df_fond], axis=0, sort=False).reset_index(drop=True)

        # увеличение площади многоугольника по мере итерации по фондам
        list_polygons = list_polygons + list(
            df_current_result.loc[~df_current_result['intersection'].map(str).str.contains('Исключена')][
                'AREA'].explode())
        current_area = cascaded_union(list_polygons)

        df_result = pd.concat([df_result, df_current_result], axis=0, sort=False).reset_index(drop=True)

    df_result[
        'mean_radius'] = mean_rad * coeff  # столбец с текущим средним радиусом по объекту, домножается на коэфф.
    df_result['min_dist'] = df_result['min_dist'] * coeff
    # расчет времени исследования с использованием PVT справочника
    dict_property = get_property(path_property)
    df_result['time_coef/objects'] = df_result.apply(
        lambda x: get_time_coef(dict_property, x.workHorizon, x.water_cut, x.oilfield, x.gasStatus),
        axis=1)
    df_result['time_coef'] = list(map(lambda x: x[0], df_result['time_coef/objects']))
    # рассчитанные средние свойства по скважинам
    # df_result['mu'] = list(map(lambda x: x[1], df_result['time_coef/objects']))
    # df_result['ct'] = list(map(lambda x: x[2], df_result['time_coef/objects']))
    # df_result['phi'] = list(map(lambda x: x[3], df_result['time_coef/objects']))
    df_result['k'] = list(map(lambda x: x[4], df_result['time_coef/objects']))  # проницаемость
    df_result['gas_visc'] = list(
        map(lambda x: x[5], df_result['time_coef/objects']))  # вязкость газа в пл. условиях
    df_result['pressure'] = list(
        map(lambda x: x[6], df_result['time_coef/objects']))  # пл. давление кгс/см2
    df_result['default_count'] = list(
        map(lambda x: x[7], df_result['time_coef/objects']))  # кол-во объектов
    # со свойствами по умолчанию
    df_result['obj_count'] = list(map(lambda x: x[8], df_result['time_coef/objects']))
    df_result['percent_of_default'] = list(
        map(lambda x: 100 * x[7] / x[8], df_result['time_coef/objects']))  # процент
    # объектов со свойствами по умолчанию
    df_result.drop(['time_coef/objects'], axis=1, inplace=True)
    # добавления столбца объектов для понимания, по какому идет расчет
    df_result['current_horizon'] = horizon
    # время исследования в сут через min расстояние
    df_result['research_time'] = (df_result['min_dist'] * df_result['min_dist'] * df_result['time_coef'])

    # отбрасывание скважин по времени исследования, если оно больше максимального
    if dict_parameters['limit_research_time']:
        df_result = df_result.loc[
            ~((df_result['well type'] == 'vertical') & (
                    df_result['research_time'] > dict_parameters['max_research_time']))]
        df_result = df_result.loc[
            ~((df_result['well type'] == 'horizontal') & (
                    df_result['research_time'] > 2 * dict_parameters['max_research_time']))]
        df_result['research_time'] = df_result.apply(
            lambda x: dict_parameters['min_research_time'] if (
                    x['well type'] == 'vertical' and x['research_time'] < dict_parameters['min_research_time']) else x[
                'research_time'], axis=1)
        df_result['research_time'] = df_result.apply(lambda x:
                                                     2 * dict_parameters['min_research_time'] if
                                                     (x['well type'] == 'horizontal' and x['research_time'] <
                                                      2 * dict_parameters['min_research_time']) else
                                                     x['research_time'], axis=1)

    df_result['oil_loss'] = 0
    df_result['gas_loss'] = 0
    df_result['injection_loss'] = 0
    df_result['oil_loss'] = df_result.apply(
        lambda x: (x.oilRate + x.condRate) * x.research_time if (
                str(x.gasStatus) == 'газоконденсатная') else x.oilRate * x.research_time, axis=1)  # потери по нефти
    df_result['gas_loss'] = df_result.apply(lambda x: (x.injectivity_day * x.research_time) if (
            str(x.gasStatus) == 'газонагнетательная') else x.gasRate * x.research_time, axis=1)  # потери по газу
    df_result['injection_loss'] = df_result['injectivity'] * df_result[
        'research_time']  # потери по закачке воды
    df_result['coverage_percentage'] = unary_union(
        list(df_result['AREA'].explode())).area / obj_square * 100
    # процент скважин в опорной сети из скважин на объекте по каждому типу
    df_result['percent_piez_wells'] = 0
    if piez_count != 0:
        df_result['percent_piez_wells'] = 100 * df_result[
            (df_result['fond'] == 'ПЬЕЗ') & (~df_result['intersection'].map(str).str.contains('Исключена'))].shape[
            0] / piez_count
    df_result['percent_inj_wells'] = 0
    if inj_count != 0:
        df_result['percent_inj_wells'] = 100 * df_result[
            (df_result['fond'] == 'НАГ') & (~df_result['intersection'].map(str).str.contains('Исключена'))].shape[
            0] / inj_count
    df_result['percent_prod_wells'] = 0
    if prod_count != 0:
        df_result['percent_prod_wells'] = 100 * df_result[
            (df_result['fond'] == 'ДОБ') & (~df_result['intersection'].map(str).str.contains('Исключена'))].shape[
            0] / prod_count
    df_result['percent_gas_wells'] = 0
    if gas_prod_count != 0:
        df_result['percent_gas_wells'] = 100 * df_result[
            (df_result['fond'] == 'ДОБ') & (df_result['gasStatus'].str.contains('газ'))].shape[0] / gas_prod_count
    df_result['year_of_survey'] = 0

    # поиск охвата проектного фонда скважинами из ОС
    if not df_proj_wells.empty:
        list_proj_research = list(check_intersection_area(cascaded_union(
            list(df_result.loc[~df_result['intersection'].map(str).str.contains('Исключена')]['AREA'].explode())),
            df_proj_wells, dict_parameters['percent'],
            dict_parameters['calc_option']))
        df_proj_wells = df_proj_wells[df_proj_wells['wellName'].isin(list_proj_research)]
        df_proj_wells['current_horizon'] = horizon
        df_result = pd.concat([df_result, df_proj_wells], axis=0, sort=False).reset_index(drop=True)

    return df_result
