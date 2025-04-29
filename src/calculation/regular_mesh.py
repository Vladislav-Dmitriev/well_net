import math
import numpy as np
import pandas as pd
from shapely.ops import unary_union
from tqdm import tqdm
from loguru import logger
from src.calculation.support_functions import get_property, get_time_coef
from src.calculation.shapely_geometry import check_intersection_area


@logger.catch(level='DEBUG')
def calc_regular_mesh(df_prod_wells, df_piez_wells, df_inj_wells, df_proj_wells, df_result, df_necessarily_wells,
                      horizon, path_property, dict_parameters, obj_square, mean_rad, coeff, list_exception, log_user):
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
    :param log_user: сигнал, передающий сообщения для пользователя в окно логирования приложения
    :return: результирующий DataFrame с опорными скважинами
    """
    # удаление исключенных скважин из DataFrame пьезометров, нагнетательных и добывающих
    log_user.emit("Удаление исключенных скважин из расчета")

    df_regular_exceptions = pd.concat(
        [df_piez_wells[df_piez_wells['wellName'].str.split("_").str[0].isin(list_exception)],
         df_inj_wells[df_inj_wells['wellName'].str.split("_").str[0].isin(list_exception)],
         df_prod_wells[df_prod_wells['wellName'].str.split("_").str[0].isin(list_exception)]],
        axis=0, sort=False).reset_index(drop=True)
    df_regular_exceptions['wellNet'] = 'В списке исключений'
    df_piez = df_piez_wells[~df_piez_wells['wellName'].str.split("_").str[0].isin(list_exception)]
    df_inj = df_inj_wells[~df_inj_wells['wellName'].str.split("_").str[0].isin(list_exception)]
    df_prod = df_prod_wells[~df_prod_wells['wellName'].str.split("_").str[0].isin(list_exception)]

    # словарь с DataFrame каждого фонда, процентом скважин в ОС и приоритетных скважин
    dict_fonds = {}
    dict_fonds['ПЬЕЗ'] = [df_piez, dict_parameters['percent_piez'],
                          df_necessarily_wells[df_necessarily_wells['fond'] == 'ПЬЕЗ']]
    dict_fonds['НАГ'] = [df_inj, dict_parameters['percent_inj'],
                         df_necessarily_wells[df_necessarily_wells['fond'] == 'НАГ']]
    dict_fonds['ДОБ'] = [df_prod, dict_parameters['percent_prod'],
                         df_necessarily_wells[df_necessarily_wells['fond'] == 'ДОБ']]
    # площадь охваченная после выбора опорных скважин
    current_area = 0
    list_polygons = []
    df_current_result = pd.DataFrame()
    # проходимся по каждому фонду (добывающий, нагнетательный, пьезометрический)
    for fond in tqdm(dict_parameters['list_order_fond'].replace(" ", "").upper().split(","), "Regular mesh for fond",
                     position=0, leave=True, colour='white', ncols=80, disable=True):
        # выделение DataFrame на фонд (добывающий, нагнетательный, пьезометрический) и процента скважин в ОС от фонда
        if fond == "ДОБ":
            log_user.emit("Построение регулярной сетки по добывающему фонду")
        elif fond == "НАГ":
            log_user.emit("Построение регулярной сетки по нагнетательному фонду")
        elif fond == "ПЬЕЗ":
            log_user.emit("Построение регулярной сетки по пьезометрическому фонду")

        df_fond = dict_fonds[fond][0]
        wellnet_percent = dict_fonds[fond][1]
        df_necessarily_fond = dict_fonds[fond][2]

        if df_fond.empty and df_necessarily_fond.empty:
            log_user.emit("Отсутствуют скважины для построения регулярной сетки")
            continue

        # условие на очистку DataFrame, если до текущей итерации уже были отобраны опорные скважины из другого фонда
        # и охватили какую-то площадь
        if current_area != 0 and not df_fond.empty:
            log_user.emit("Исключение из расчета скважин текущего фонда, охваченных регулярной сеткой предыдущего шага")
            df_fond = df_fond[~df_fond['wellName'].isin(list(check_intersection_area(current_area, df_fond,
                                                                                     dict_parameters['percent'],
                                                                                     dict_parameters['calc_option'])))]

        list_check_well = []
        if df_fond.shape[0] > 0:
            df_fond['intersection'] = list(
                map(lambda x, y: check_intersection_area(x, df_fond[df_fond.wellName.str.split("_").str[0] != y],
                                                         dict_parameters['percent'],
                                                         dict_parameters['calc_option']),
                    df_fond.AREA, df_fond.wellName.str.split("_").str[0]))

            df_fond['number'] = df_fond['intersection'].apply(lambda x: np.size(x))
            df_fond = df_fond.sort_values(by=['number', 'oilRate'], axis=0, ascending=[False, True])
            list_optim = list(df_fond['wellName'].str.split("_").str[0].explode())
            while len(list_optim) != 0:
                if (len(df_fond['intersection'].explode().unique()) == 1) and (
                        math.isnan(df_fond['intersection'].explode().unique()[0])):
                    list_check_well += list_optim.copy()
                    break
                list_check_well += [list_optim[0]]
                list_exception = [list_optim[0]] + list(set(part for item in df_fond[
                    df_fond['wellName'].str.split("_").str[0] == list_optim[0]]['intersection'].values[0] for part in
                                                            item.split("_")))
                list_optim = [x for x in list_optim if x not in list_exception]
            list_check_well = list(set(list_check_well))
            # добавление обязательных скважин к результирующему DataFrame
            df_current_result = df_fond[df_fond['wellName'].str.split("_").str[0].isin(list_check_well)]
            df_current_result = pd.concat([df_necessarily_fond, df_current_result], axis=0, sort=False).reset_index(
                drop=True)
        elif df_fond.empty and not df_necessarily_fond.empty:
            df_current_result = pd.concat([df_necessarily_fond, df_current_result], axis=0, sort=False).reset_index(
                drop=True)
        else:
            continue

        # проверка на корректность процента по текущему фонду
        if wellnet_percent is None:
            # увеличение площади многоугольника по мере итерации по фондам
            list_polygons = list_polygons + list(df_current_result['AREA'].explode())
            current_area = unary_union(list_polygons)
            df_result = pd.concat([df_result, df_current_result], axis=0, sort=False).reset_index(drop=True)
            df_result['wellNet'] = 'Выбрана в опорную сеть'
            continue

        # функция проверки процента скважин в опорной сети от текущего фонда
        count_target = math.ceil(wellnet_percent / 100 * (df_fond.shape[0] + df_necessarily_fond.shape[0]))
        log_user.emit(f"Целевое число скважин фонда в регулярной сетке: {count_target}")
        if (df_current_result.shape[0] > count_target) and (dict_parameters['option_percent']):
            # сортировка части DataFrame без обязательных скважин по возрастанию дебита нефти и убыванию пересечений
            df_current_result.loc[~df_current_result['num_of_research']] = df_current_result.loc[
                ~df_current_result['num_of_research']].sort_values(by=['number', 'oilRate'], axis=0,
                                                                   ascending=[False, True])
            list_out_wellnet = df_current_result[
                               -(df_current_result.shape[0] - count_target):].wellName.explode().unique()
            df_current_result['wellNet'] = 'Выбрана в опорную сеть'
            df_current_result.loc[
                df_current_result['wellName'].isin(list_out_wellnet), 'wellNet'] = 'Исключена из опорной сети'
        # добавить недостающие скважины в ОС
        elif (df_current_result.shape[0] < count_target) and (dict_parameters['option_percent']):
            df_fond = df_fond[~df_fond['wellName'].isin(list(df_current_result['wellName'].explode().unique()))]
            df_fond = df_fond.sort_values(by=['number', 'oilRate'], axis=0, ascending=[True, True])
            df_fond = df_fond[:(count_target - df_current_result.shape[0])]
            df_current_result = pd.concat([df_current_result, df_fond], axis=0, sort=False).reset_index(drop=True)
            df_current_result['wellNet'] = 'Выбрана в опорную сеть'
        else:
            df_current_result['wellNet'] = 'Выбрана в опорную сеть'

        # увеличение площади многоугольника по мере итерации по фондам
        list_polygons = list_polygons + list(
            df_current_result.loc[~df_current_result['wellNet'].map(str).str.contains('Исключена')][
                'AREA'].explode())
        current_area = unary_union(list_polygons)
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
    df_result.loc[df_result['fond'] == 'ПЬЕЗ', 'research_time'] = 0

    # применение условий на временные рамки исследования скважин
    if dict_parameters['limit_research_time'] and (dict_parameters['min_research_time'] != ''):
        log_user.emit("Учет условия минимального времени исследования скважин")
        df_result['research_time'] = df_result.apply(
            lambda x: dict_parameters['min_research_time'] if (
                    x['well type'] == 'vertical' and x['research_time'] < dict_parameters['min_research_time']) else
            x['research_time'], axis=1)
        df_result['research_time'] = df_result.apply(lambda x:
                                                     2 * dict_parameters['min_research_time'] if
                                                     (x['well type'] == 'horizontal' and x['research_time'] <
                                                      2 * dict_parameters['min_research_time']) else
                                                     x['research_time'], axis=1)

    if dict_parameters['limit_research_time'] and (dict_parameters['max_research_time'] != ''):
        log_user.emit("Учет условия максимального времени исследования скважин")
        df_result['research_time'] = df_result.apply(
            lambda x: dict_parameters['max_research_time'] if (
                    x['well type'] == 'vertical' and x['research_time'] > dict_parameters['max_research_time']) else
            x['research_time'], axis=1)
        df_result['research_time'] = df_result.apply(
            lambda x: 2 * dict_parameters['max_research_time'] if (
                    x['well type'] == 'horizontal' and x['research_time'] > 2 * dict_parameters['max_research_time']) else
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
    # кол-во скважин в каждом фонде для определения процента вхождения в ОС
    inj_count = df_inj.shape[0] + df_necessarily_wells[df_necessarily_wells['fond'] == 'НАГ'].shape[0]
    prod_count = df_prod.shape[0] + df_necessarily_wells[df_necessarily_wells['fond'] == 'ДОБ'].shape[0]
    piez_count = df_piez.shape[0] + df_necessarily_wells[df_necessarily_wells['fond'] == 'ПЬЕЗ'].shape[0]
    gas_prod_count = df_prod[df_prod['gasStatus'].str.contains('газ')].shape[0] + df_necessarily_wells[
        (df_necessarily_wells['fond'] == 'ДОБ') & (df_necessarily_wells['gasStatus'].str.contains('газ'))].shape[0]
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

    # присоединение к таблице результатов скважин из списка исключений и охваченных зоной исследования предыдущего фонда
    list_covered_wells = list(
        df_result[df_result['wellNet'] == 'Выбрана в опорную сеть']['intersection'].explode().unique())
    df_result = pd.concat([df_result, df_piez[df_piez['wellName'].isin(list_covered_wells)],
                           df_inj[df_inj['wellName'].isin(list_covered_wells)],
                           df_prod[df_prod['wellName'].isin(list_covered_wells)],
                           df_regular_exceptions], axis=0, sort=False).reset_index(drop=True)
    df_result.loc[df_result['wellNet'].isnull(), 'wellNet'] = 'Охвачена исследованиями'
    df_result.loc[df_result['current_horizon'].isnull(), 'current_horizon'] = horizon
    # поиск охвата проектного фонда скважинами из ОС
    if not df_proj_wells.empty:
        list_proj_research = list(check_intersection_area(unary_union(
            list(df_result.loc[df_result['wellNet'] == 'Выбрана в опорную сеть']['AREA'].explode())),
            df_proj_wells, dict_parameters['percent'],
            dict_parameters['calc_option']))
        df_proj_wells.loc[df_proj_wells['wellName'].isin(list_proj_research), 'wellNet'] = 'Охвачена исследованиями'
        df_proj_wells.loc[df_proj_wells['wellNet'].isnull(), 'wellNet'] = 'Не охвачена исследованиями'
        df_proj_wells['current_horizon'] = horizon
        df_result = pd.concat([df_result, df_proj_wells], axis=0, sort=False).reset_index(drop=True)

    return df_result
