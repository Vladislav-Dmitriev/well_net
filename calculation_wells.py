import geopandas as gpd
import pandas as pd
from loguru import logger
from tqdm import tqdm

from FirstRowWells import mean_radius
from functions import (intersect_number, optimization, check_intersection_area,
                       unpack_status, add_shapely_types, get_time_coef)


def piez_calc(df_piez_wells, hor_prod_wells, df_result, percent):
    """
    Функция обрабатывает DataFrame из пьезометров, подающийся на вход
    :param percent: процент длины траектории скважины для включения в зону охвата
    :param df_piez_wells: DataFrame из пьезометров, выделенный из входного файла
    :param hor_prod_wells: DataFrame из добывающих скважин
    :param df_result: В функцию подается DataFrame df_result для добавления в общий результат расчета пьезометров
    :return: Возвращаются: 1) список скважин, не имеющих пересечений;
                           2) DataFrame пьезометров;
                           3) DataFrame добывающих;
                           4) Общий DataFrame со всеми результатами расчета по объекту
    """
    logger.info("Calculation of piezometers")
    if not df_piez_wells.empty:

        # check_intersection
        hor_prod_wells, df_piez_wells = intersect_number(hor_prod_wells, df_piez_wells, percent)

        # !!!OPTIMIZATION!!!
        list_piez_wells = optimization(hor_prod_wells, df_piez_wells)

        # final list of piezometers to result_df
        df_result = pd.concat([df_result, df_piez_wells[df_piez_wells.wellName.isin(list_piez_wells)]],
                              axis=0, sort=False).reset_index(drop=True)

        # wells without communication with piezometer
        isolated_wells = hor_prod_wells[hor_prod_wells.number == 0].wellName.values
        hor_prod_wells.drop(["intersection", "number"], axis=1, inplace=True)
    else:
        isolated_wells = hor_prod_wells.wellName.values
    return isolated_wells, df_piez_wells, hor_prod_wells, df_result


def inj_calc(isolated_wells, hor_prod_wells, df_inj_wells, df_result, percent):
    """
    Функция обарабатывает DataFrame нагнетательных скважин
    :param percent: процент длины траектории скважины для включения в зону охвата
    :param isolated_wells: Список скважин, не имеюших пересечений
    :param hor_prod_wells: DataFrame добывающих скважин
    :param df_inj_wells: DataFrame нагнетательных скважин
    :param df_result: Результирующий DataFrame, к которому добавится результат обработки DataFrame нагнетательных скв.
    :return: Возвращаются: 1) список скважин, не имеющих пересечений;
                           2) DataFrame нагнетательных;
                           3) DataFrame добывающих;
                           4) Общий DataFrame со всеми результатами расчета по объекту
    """
    logger.info("Calculation of injection wells")
    hor_prod_wells = hor_prod_wells[hor_prod_wells.wellName.isin(isolated_wells)]

    if not df_inj_wells.empty:

        # check_intersection
        hor_prod_wells, df_inj_wells = intersect_number(hor_prod_wells, df_inj_wells, percent)

        # !!!OPTIMIZATION!!!
        list_inj_wells = optimization(hor_prod_wells, df_inj_wells)

        # final list of injection to result_df
        df_result = pd.concat([df_result, df_inj_wells[df_inj_wells.wellName.isin(list_inj_wells)]],
                              axis=0, sort=False).reset_index(drop=True)

        # wells without communication with injection wells
        isolated_wells = hor_prod_wells[hor_prod_wells.number == 0].wellName.values

        hor_prod_wells.drop(["intersection", "number"], axis=1, inplace=True)
    else:
        isolated_wells = hor_prod_wells.wellName.values

    return isolated_wells, hor_prod_wells, df_inj_wells, df_result


def single_calc(isolated_wells, hor_prod_wells, df_result, percent):
    """
    Функция обарабатывает DataFrame одиночных скважин
    :param percent: процент длины траектории скважины для включения в зону охвата
    :param isolated_wells: Список скважин, не имеюших пересечений
    :param hor_prod_wells: DataFrame добывающих скважин
    :param df_result: Результирующий DataFrame, к которому добавится результат обработки DataFrame одиночных скв.
    :return: Возвращаются: 1) список скважин, не имеющих пересечений;
                           2) DataFrame добывающих;
                           3) Общий DataFrame со всеми результатами расчета по объекту
    """
    logger.info("Calculation of single wells")
    single_wells = []
    hor_prod_wells = hor_prod_wells[hor_prod_wells.wellName.isin(isolated_wells)]

    # check_intersection
    hor_prod_wells.insert(loc=hor_prod_wells.shape[1], column="intersection",
                          value=list(map(lambda x, y:
                                         check_intersection_area(x, hor_prod_wells[hor_prod_wells.wellName != y],
                                                                 percent, True),
                                         hor_prod_wells.AREA, hor_prod_wells.wellName)))
    hor_prod_wells.insert(loc=hor_prod_wells.shape[1], column="number",
                          value=list(map(lambda x: len(x), hor_prod_wells.intersection)))

    single_wells += list(hor_prod_wells[hor_prod_wells.number == 0].wellName)

    df_optim = hor_prod_wells[hor_prod_wells.number > 0]

    # !!!OPTIMIZATION!!!
    if not df_optim.empty:
        df_optim = df_optim.sort_values(by=['oilRate'], ascending=True)
        list_wells = df_optim.wellName.values
        while len(list_wells) != 0:
            single_wells += [list_wells[0]]
            list_exeption = [list_wells[0]] + \
                            list(df_optim[df_optim.wellName == list_wells[0]].intersection.explode().unique())
            list_wells = [x for x in list_wells if x not in list_exeption]

    # final list of injection to result_df
    df_result = pd.concat(
        [df_result, hor_prod_wells[hor_prod_wells.wellName.isin(single_wells)]],
        axis=0, sort=False).reset_index(drop=True)

    return single_wells, hor_prod_wells, df_result


def dict_keys(list_r, contour_name):
    """
    :param list_r: список коэффициентов для умножения радиуса
    :param contour_name: имя контура
    :return: словарь с ключами из коэффициентов и имени текущего контура
    """
    list_keys = [f'{contour_name}, k = {x}' for x in list_r]
    dict_result = dict.fromkeys(list_keys, [pd.DataFrame(), None])
    return dict_result


def calc_contour(separation, limit_coef, polygon, df_in_contour, contour_name, max_distance,
                 path_property, list_mult_coef, percent, *angle_parameters, **dict_constant):
    """
    Функция для расчета скважин, включающая в себя все функции расчета отдельных типов скважин
    :param separation: кол-во лет, на которые распределяются исследования скважин в "слепых" зонах
    :param limit_coef: максимальный коэффициент кратного увеличения радиуса охвата, больше которого начинается выделение
    "слепых" зон и скважин в них
    :param polygon: многоугольник из координат текущего контура
    :param percent: процент длины траектории скважины для включения в зону охвата
    :param list_mult_coef: список коэффициентов домножения среднего радиуса
    :param path_property: путь к файлу с параметрами
    :param df_in_contour: DataFrame, полученные из исходного файла со свкажинами
    :param max_distance: в случае, когда скважины находятся друг от друга на расстоянии больше максимального,
    средним радиусом в этом случае для построения области взаимодействия будет заданное максимальное расстояние
    :param contour_name: Название файла с координатами текущего контура без расширения файла
    :param dict_constant: Словарь с характером работы и состоянием скажины
    :return: Возвращается словарь с добавленным ключом по коэффициенту умножения радиуса охвата
    """
    dict_result = dict_keys(list_mult_coef, contour_name)
    PROD_STATUS, PROD_MARKER, PIEZ_STATUS, INJ_MARKER, INJ_STATUS = unpack_status(dict_constant)
    list_objects = df_in_contour.workHorizon.str.replace(" ", "").str.split(",").explode().unique()
    list_objects.sort()

    for horizon in tqdm(list_objects, "Calculation for objects", position=0, leave=False,
                        colour='green', ncols=80):
        logger.info(f'Current horizon: {horizon}')
        # для каждого объекта определяется свой df_horizon_input
        df_horizon_input = df_in_contour[
            list(map(lambda x: len(set(x.replace(" ", "").split(",")) & set([horizon])) > 0,
                     df_in_contour.workHorizon))]
        mean_rad = mean_radius(df_horizon_input, angle_parameters[0], angle_parameters[1],
                               angle_parameters[2], angle_parameters[3], max_distance)
        logger.info(f'Radius: {mean_rad}')

        for key, coeff in zip(dict_result, list_mult_coef):
            logger.info(f'Add shapely types with coefficient = {coeff}')
            df_horizon_input = add_shapely_types(df_horizon_input, mean_rad, coeff)
            # выделение продуктивных, нагнетательных и исследуемых скважин для объекта
            df_prod_wells = df_horizon_input.loc[(df_horizon_input.workMarker == PROD_MARKER)
                                                 & (df_horizon_input.wellStatus.isin(PROD_STATUS))]
            df_piez_wells = df_horizon_input.loc[df_horizon_input.wellStatus == PIEZ_STATUS]
            df_inj_wells = df_horizon_input.loc[(df_horizon_input.workMarker == INJ_MARKER)
                                                & (df_horizon_input.wellStatus.isin(INJ_STATUS))]

            logger.info(f'Key of dictionary: {key}, Mult coefficient: {coeff}')
            df_result = pd.DataFrame()

            if df_prod_wells.empty:
                continue

            df_result = calc_horizon(path_property, percent, mean_rad, coeff, horizon,
                                     df_piez_wells, df_prod_wells, df_inj_wells, df_result)
            df_result['year_of_survey'] = 0

            if (coeff > limit_coef) and (separation is not None):
                df_result_invisible = pd.DataFrame()
                df_prod_intersection = df_prod_wells[df_prod_wells['wellName'].isin(list(
                    set(df_result['intersection'].explode().unique())))]  # выделение DataFrame продуктивных скважин

                list_invisible_wells = get_invisible_wells(df_result.copy(), df_prod_intersection,
                                                           percent, mean_rad, limit_coef)  # скважины в слепой зоне
                if not list_invisible_wells:
                    logger.info(f'Write to result dictionary by key {key}, there are not invisible wells')
                    dict_result[key] = [pd.concat([dict_result[key][0], df_result],
                                                  axis=0, sort=False).reset_index(drop=True), polygon]
                    continue
                df_prod_recalc = add_shapely_types(
                    df_prod_intersection[df_prod_intersection['wellName'].isin(list_invisible_wells)],
                    mean_rad, limit_coef)
                df_horizon_recalc = add_shapely_types(df_horizon_input, mean_rad, limit_coef)
                df_piez_recalc = df_horizon_recalc.loc[df_horizon_recalc.wellStatus == PIEZ_STATUS]
                df_inj_recalc = df_horizon_recalc.loc[(df_horizon_recalc.workMarker == INJ_MARKER)
                                                      & (df_horizon_recalc.wellStatus.isin(INJ_STATUS))]
                df_result_invisible = calc_horizon(path_property, percent, mean_rad, limit_coef, horizon,
                                                   df_piez_recalc, df_prod_recalc, df_inj_recalc, df_result_invisible)
                if separation == 1:
                    df_result_invisible['year_of_survey'] = 1
                    df_result = pd.concat([df_result, df_result_invisible],
                                          axis=0, sort=False).reset_index(drop=True)
                elif separation == 2:
                    df_first_year, df_second_year = separation_gdis(df_result_invisible)
                    df_first_year['year_of_survey'], df_second_year['year_of_survey'] = 1, 2
                    df_result = pd.concat([df_result, df_first_year, df_second_year],
                                          axis=0, sort=False).reset_index(drop=True)
                else:
                    pass
            logger.info(f'Write to result dictionary by key {key}')
            dict_result[key] = [pd.concat([dict_result[key][0], df_result],
                                          axis=0, sort=False).reset_index(drop=True), polygon]

    return dict_result


def calc_horizon(path_property, percent, mean_rad, coeff, horizon,
                 df_piez_wells, df_prod_wells, df_inj_wells, df_result):
    """
    Функция для расчета результирующего DataFrame по объекту
    :param path_property: путь к файлу со свойствами
    :param percent: процент длины траектории скважины для включения в зону охвата
    :param mean_rad: средний радиус по объекту
    :param coeff: коэффициент кратного увеличения радиуса
    :param horizon: объект, по которому идет расчет
    :param df_piez_wells: пьезометры по текущему объекту
    :param df_prod_wells: добывающие скавжины по текущему объекту
    :param df_inj_wells: нагнетательные скважины по текущему объекту
    :param df_result: пустой DataFrame, в который записывается результат расчета
    :return: результирующий DataFrame по объекту
    """
    logger.info(f'Calculation for {horizon}')
    # I. Piezometric wells_____________________________________________________________________________________

    isolated_wells, df_piez_wells, hor_prod_wells, df_result = piez_calc(df_piez_wells,
                                                                         df_prod_wells.copy(),
                                                                         df_result, percent)

    # II. Injection wells______________________________________________________________________________________
    if len(isolated_wells):
        isolated_wells, hor_prod_wells, df_inj_wells, df_result = inj_calc(isolated_wells,
                                                                           hor_prod_wells,
                                                                           df_inj_wells,
                                                                           df_result, percent)

        # III. Single wells____________________________________________________________________________________
        if len(isolated_wells):
            single_wells, hor_prod_wells, df_result = single_calc(isolated_wells,
                                                                  hor_prod_wells,
                                                                  df_result, percent)

    df_result['mean_radius'] = mean_rad * coeff  # столбец с текущим стредним радиусом по объекту, дамножается на коэфф.
    # коэффициент для расчета времени исследования
    df_result['time_coef'] = df_result['workHorizon'].apply(lambda x:
                                                            get_time_coef(path_property, list(x.split(',')),
                                                                          'mu', 'ct', 'phi', 'k'))
    df_result['current_horizon'] = horizon  # добавления столбца объектов для понимания, по какому идет расчет
    df_result['research_time'] = (df_result['mean_radius'] * df_result['mean_radius']
                                  * df_result['time_coef'] / 24)  # время исследования
    df_result['oil_loss'] = df_result['oilRate'] * df_result['research_time']  # потери по нефти
    df_result['injection_loss'] = df_result['injectivity'] * df_result['research_time']  # потери по закачке

    return df_result


def get_invisible_wells(df_recalc, df_prod, percent, radius, coeff):
    """
    Функция получения скважин в слепой зоне при k > 1.5 (k*R)
    :param coeff: коэффициент домножения радиуса
    :param df_recalc: копия результирующего DataFrame для выделения скважин в слепой зоне
    :param df_prod: DataFrame добывающих скважин
    :param percent: процент перекрытия зоной охвата, при котором скважина попадает в нее
    :param radius: максимальный радиус охвата в слепой зоне
    :return: возвращает список скважин для дообследования и DataFrame с обновленным столбцом пересечений
    """
    logger.info("Search invisible wells")
    df_recalc['intersection_kR'] = df_recalc['intersection']
    df_recalc['intersection'] = 0
    df_recalc['AREA'] = 0
    df_recalc = add_shapely_types(df_recalc, radius, coeff)
    df_recalc['intersection'] = list(map(lambda x: check_intersection_area(x, df_prod, percent, True),
                                         df_recalc.AREA))
    intersect_kR, intersect_R = (set(df_recalc['intersection_kR'].explode().unique()),
                                 set(df_recalc['intersection'].explode().unique()))
    intersect_kR = {x for x in intersect_kR if pd.notna(x)}
    intersect_R = {x for x in intersect_R if pd.notna(x)}
    list_invisible_wells = list(intersect_kR - intersect_R)

    return list_invisible_wells


def separation_gdis(df_invisible):
    """
    Функция разделения скважин в слепых зонах на 2 года
    :param df_invisible: DataFrame скважин, которые попали в слепую зону
    :return: Возвращает два DataFrame, по которым распределены скаважины в слепой зоне(каждая вторая)
    """
    logger.info("Separation invisible wells on 2 years")
    df_invisible = gpd.GeoDataFrame(df_invisible, geometry='GEOMETRY')
    df_invisible['dist_from_0'] = list(map(lambda x: x.distance(df_invisible['GEOMETRY'].iloc[0]),
                                           df_invisible['GEOMETRY']))
    df_invisible.sort_values(by=['dist_from_0'], ascending=True)
    list_separation = list(set(df_invisible.wellName.explode().unique()))
    list_first_year = []
    list_second_year = []
    for i in tqdm(range(1, len(list_separation), 2), "Separation"):
        list_second_year += list_separation[i]
        list_first_year += list_separation[i - 1]
    df_invisible.drop(['dist_from_0'], axis=1, inplace=True)

    return (df_invisible[df_invisible['wellName'].isin(list_first_year)],
            df_invisible[df_invisible['wellName'].isin(list_second_year)])
