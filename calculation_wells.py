import geopandas as gpd
import pandas as pd
from loguru import logger
from shapely.ops import unary_union
from tqdm import tqdm

from FirstRowWells import mean_radius
from functions import unpack_status, get_time_coef, get_property
from geometry import intersect_number, optimization, check_intersection_area, add_shapely_types


# def calculation(df_input, marker):
#     if marker == 'optimize':
#         return calc_contour()
#     elif marker == 'regular':
#         return calc_regular_mesh()
#     else:
#         raise NameError(f'Wrong marker name: {marker}')


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


def single_calc(list_exception, isolated_wells, hor_prod_wells, df_result, percent):
    """
    Функция обарабатывает DataFrame одиночных скважин
    :param list_exception: список исключаемых из расчета скважин
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
    df_prod_wells = hor_prod_wells.copy()
    hor_prod_wells = hor_prod_wells[hor_prod_wells.wellName.isin(isolated_wells)]

    # check_intersection
    hor_prod_wells.insert(loc=hor_prod_wells.shape[1], column="intersection",
                          value=list(map(lambda x, y:
                                         check_intersection_area(x, hor_prod_wells[hor_prod_wells.wellName != y],
                                                                 percent, True),
                                         hor_prod_wells.AREA, hor_prod_wells.wellName)))
    hor_prod_wells.insert(loc=hor_prod_wells.shape[1], column="number",
                          value=list(map(lambda x: len(x), hor_prod_wells['intersection'])))

    # delete exception wells
    list_prod_exception = list(set(list_exception).intersection(hor_prod_wells['wellName'].explode().unique()))
    hor_prod_wells = hor_prod_wells[~hor_prod_wells['wellName'].isin(list_prod_exception)]

    single_wells += list(hor_prod_wells[hor_prod_wells['number'] == 0].wellName)

    df_optim = hor_prod_wells[hor_prod_wells.number > 0]

    # !!!OPTIMIZATION!!!
    if not df_optim.empty:
        df_optim = df_optim.sort_values(by=['oilRate'], ascending=True)
        list_wells = df_optim.wellName.values
        while len(list_wells) != 0:
            single_wells += [list_wells[0]]
            list_exeption = [list_wells[0]] + \
                            list(df_optim[df_optim['wellName'] == list_wells[0]]['intersection'].explode().unique())
            list_wells = [x for x in list_wells if x not in list_exeption]

    # final list of injection to result DataFrame
    clean_single_wells = []
    df = hor_prod_wells[hor_prod_wells['wellName'].isin(single_wells)]

    # delete duplicates
    clean_single_wells += list(set(df['wellName']).difference(set(df['intersection'].explode().unique())))
    df = df[df.wellName.isin(clean_single_wells)]

    list_exception_intersect = list(set(list_prod_exception).difference(set(df['intersection'].explode().unique())))
    if len(list_exception_intersect):
        df_exception = df_prod_wells[df_prod_wells['wellName'].isin(list_exception_intersect)]
        df_exception['intersection'] = 0
        df_exception['number'] = 0
        df_exception['intersection'] = df_exception['intersection'].apply(lambda x: 'Не охвачены исследованием!!!')
        df_exception['number'] = df_exception['number'].apply(lambda x: 0)
        df = pd.concat([df, df_exception], axis=0, sort=False).reset_index(drop=True)

    # delete duplicates
    clean_wells = []
    clean_wells += list(set(df['wellName']).difference(set(df['intersection'].explode().unique())))
    df = df[df.wellName.isin(clean_wells)]

    df_result = pd.concat([df_result, df], axis=0, sort=False).reset_index(drop=True)

    return clean_wells, hor_prod_wells, df_result


def dict_keys(list_r, contour_name):
    """
    :param list_r: список коэффициентов для умножения радиуса
    :param contour_name: имя контура
    :return: словарь с ключами из коэффициентов и имени текущего контура
    """
    list_keys = [f'{contour_name}, k = {x}' for x in list_r]
    dict_result = dict.fromkeys(list_keys, [pd.DataFrame(), None])
    return dict_result


def calc_contour(polygon, df_in_contour, contour_name, path_property, list_exception, dict_parameters, **dict_constant):
    """
    Функция для расчета скважин, включающая в себя все функции расчета отдельных типов скважин
    :param dict_parameters: словарь с параметрами (коэффициенты на радиус, углы перекрытия и тд)
    :param list_exception: список исключаемых из расчета скважин
    "слепых" зон и скважин в них
    :param polygon: многоугольник из координат текущего контура
    :param path_property: путь к файлу с параметрами
    :param df_in_contour: DataFrame, полученные из исходного файла со свкажинами
    средним радиусом в этом случае для построения области взаимодействия будет заданное максимальное расстояние
    :param contour_name: Название файла с координатами текущего контура без расширения файла
    :param dict_constant: Словарь с характером работы и состоянием скажины
    :return: Возвращается словарь с добавленным ключом по коэффициенту умножения радиуса охвата
    """
    dict_result = dict_keys(dict_parameters['mult_coef'], contour_name)

    list_objects = list(set(df_in_contour.workHorizon.str.replace(" ", "").str.split(",").explode()))
    list_objects.sort()
    for horizon in tqdm(list_objects, "Calculation for objects", position=0, leave=True,
                        colour='white', ncols=80):
        logger.info(f'Current horizon: {horizon}')
        # для каждого объекта определяется свой df_horizon_input
        df_horizon_input = df_in_contour[
            list(map(lambda x: len(set(x.replace(" ", "").split(",")) & set([horizon])) > 0,
                     df_in_contour.workHorizon))]
        # calculate mean oil rate by current object
        mean_oilrate = df_horizon_input[df_horizon_input['oilRate'] != 0].oilRate.mean()
        # calculate mean radius by object and minimum radius for every well
        mean_rad, df_horizon_input = mean_radius(df_horizon_input, dict_parameters['verticalWellAngle'],
                                                 dict_parameters['MaxOverlapPercent'],
                                                 dict_parameters['angle_horizontalT1'],
                                                 dict_parameters['angle_horizontalT3'], dict_parameters['max_distance'])
        logger.info(f'Research radius for horizon {horizon} calculated')

        # площадь многоугольника построенного по крайним скважинам, попавшим на расчет
        obj_square = unary_union(list(df_horizon_input['GEOMETRY'].explode())).convex_hull
        obj_square = (obj_square.buffer(mean_rad)).area  # площадь охватывающая все скважины объекта, попавшие на расчет

        for key, coeff in zip(dict_result, dict_parameters['mult_coef']):
            logger.info(f'Add shapely types with coefficient = {coeff}')
            df_horizon_input = add_shapely_types(df_horizon_input, mean_rad, coeff)
            # выделение продуктивных, нагнетательных и исследуемых скважин для объекта
            df_prod_wells = df_horizon_input.loc[(df_horizon_input['fond'] == 'ДОБ') &
                                                 (df_horizon_input['oilRate'] <= mean_oilrate)]
            df_piez_wells = df_horizon_input.loc[df_horizon_input['fond'] == 'ПЬЕЗ']
            df_inj_wells = df_horizon_input.loc[df_horizon_input['fond'] == 'НАГ']
            logger.info(f'Key of dictionary: {key}, Mult coefficient: {coeff}')
            df_result = pd.DataFrame()

            if df_prod_wells.empty:  # если DataFrame с добывающими скважинами пустой, то вычисления по объекту нет
                continue

            df_result = calc_horizon(list_exception, path_property, dict_parameters['percent'], mean_rad, coeff,
                                     horizon, obj_square, dict_parameters['min_research_time'],
                                     dict_parameters['max_research_time'], df_piez_wells, df_prod_wells,
                                     df_inj_wells, df_result, dict_constant)
            df_result['year_of_survey'] = 0  # для скважин первой итерации расчета год исследования ставится текущий

            if (coeff > dict_parameters['limit_radius_coef']) and (dict_parameters['separation_by_years'] is not None):
                df_result_invisible = pd.DataFrame()
                # выделение охваченных исследованиями добывающих скважин результата первой итерации расчета из исходного
                # DataFrame добывающих скважин
                df_prod_intersection = df_prod_wells[df_prod_wells['wellName'].isin(list(
                    set(df_result['intersection'].explode().unique())))]

                list_invisible_wells = get_invisible_wells(df_result.copy(), df_prod_intersection,
                                                           dict_parameters['percent'], mean_rad, dict_parameters[
                                                               'limit_radius_coef'])  # список скважин в слепой зоне
                if not list_invisible_wells:
                    logger.info(f'Write to result dictionary by key {key}, there are not invisible wells')
                    dict_result[key] = [pd.concat([dict_result[key][0], df_result],
                                                  axis=0, sort=False).reset_index(drop=True), polygon]
                    continue
                # выделение DataFrame добывающих скважин в слепых зонах из исходного DataFrame продуктивных
                df_prod_recalc = add_shapely_types(
                    df_prod_intersection[df_prod_intersection['wellName'].isin(list_invisible_wells)],
                    mean_rad, dict_parameters['limit_radius_coef'])
                # обновление столбца AREA с максимальным R в DataFrame скважин, попавших на первую итерацию расчета
                df_horizon_recalc = add_shapely_types(df_horizon_input, mean_rad, dict_parameters['limit_radius_coef'])
                df_piez_recalc = df_horizon_recalc.loc[df_horizon_recalc['fond'] == 'ПЬЕЗ']
                df_inj_recalc = df_horizon_recalc.loc[df_horizon_recalc['fond'] == 'НАГ']
                df_result_invisible = calc_horizon(list_exception, path_property, dict_parameters['percent'], mean_rad,
                                                   coeff, horizon, obj_square, dict_parameters['min_research_time'],
                                                   dict_parameters['max_research_time'], df_piez_recalc, df_prod_recalc,
                                                   df_inj_recalc, df_result_invisible, dict_constant)
                if dict_parameters['separation_by_years'] == 1:
                    df_result_invisible['year_of_survey'] = 1
                    df_result = pd.concat([df_result, df_result_invisible],
                                          axis=0, sort=False).reset_index(drop=True)
                elif dict_parameters['separation_by_years'] == 2:
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


def calc_horizon(list_prod_exception, path_property, percent, mean_rad, coeff, horizon,
                 obj_square, min_time_research, max_time_research, df_piez_wells, df_prod_wells, df_inj_wells,
                 df_result, dict_constant):
    """
    Функция для расчета результирующего DataFrame по объекту
    :param obj_square: площадь объекта месторождения по краевым скважинам
    :param dict_constant: словарь со статусами работы скважин
    :param list_prod_exception: список исключаемых из расчета скважин
    :param path_property: путь к файлу со свойствами
    :param percent: процент длины траектории скважины для включения в зону охвата
    :param mean_rad: средний радиус по объекту
    :param coeff: коэффициент кратного увеличения радиуса
    :param horizon: объект, по которому идет расчет
    :param df_piez_wells: пьезометры по текущему объекту
    :param df_prod_wells: добывающие скважины по текущему объекту
    :param df_inj_wells: нагнетательные скважины по текущему объекту
    :param df_result: пустой DataFrame, в который записывается результат расчета
    :return: результирующий DataFrame по объекту
    """
    inj_count = df_inj_wells.shape[0]
    prod_count = df_prod_wells.shape[0]
    piez_count = df_piez_wells.shape[0]

    PROD_STATUS, PROD_MARKER, PIEZ_STATUS, INJ_MARKER, INJ_STATUS, DELETE_MARKER = unpack_status(dict_constant)
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
            single_wells, hor_prod_wells, df_result = single_calc(list_prod_exception,
                                                                  isolated_wells,
                                                                  hor_prod_wells,
                                                                  df_result, percent)

    df_result['mean_radius'] = mean_rad * coeff  # столбец с текущим средним радиусом по объекту, домножается на коэфф.
    df_result['min_dist'] = df_result['min_dist'] * coeff
    # коэффициент для расчета времени исследования
    dict_property = get_property(path_property)
    df_result['time_coef/objects'] = df_result.apply(
        lambda x: get_time_coef(dict_property, x.workHorizon, x.water_cut, x.oilfield, x.gasStatus), axis=1)
    df_result['time_coef'] = list(map(lambda x: x[0], df_result['time_coef/objects']))
    # df_result['mu'] = list(map(lambda x: x[1], df_result['time_coef/objects']))
    # df_result['ct'] = list(map(lambda x: x[2], df_result['time_coef/objects']))
    # df_result['phi'] = list(map(lambda x: x[3], df_result['time_coef/objects']))
    df_result['k'] = list(map(lambda x: x[4], df_result['time_coef/objects']))  # проницаемость
    df_result['gas_visc'] = list(map(lambda x: x[5], df_result['time_coef/objects']))  # вязкость газа в пл. условиях
    df_result['pressure'] = list(map(lambda x: x[6], df_result['time_coef/objects']))  # пл. давление кгс/см2
    df_result['default_count'] = list(map(lambda x: x[7], df_result['time_coef/objects']))  # кол-во объектов
    # со свойствами по умолчанию
    df_result['obj_count'] = list(map(lambda x: x[8], df_result['time_coef/objects']))
    df_result['percent_of_default'] = list(map(lambda x: 100 * x[5] / x[6], df_result['time_coef/objects']))  # процент
    # объектов со свойствами по умолчанию
    df_result.drop(['time_coef/objects'], axis=1, inplace=True)
    df_result['current_horizon'] = horizon  # добавления столбца объектов для понимания, по какому идет расчет
    df_result['research_time'] = (df_result['min_dist'] * df_result['min_dist']
                                  * df_result['time_coef'])  # время исследования в сут через min расстояние

    # # filter and delete wells, which don't fit the parameters limit research time
    # df_result = df_result.loc[
    #     ~((df_result['well type'] == 'vertical') & (df_result['research_time'] > max_time_research))]
    # df_result = df_result.loc[
    #     ~((df_result['well type'] == 'horizontal') & (df_result['research_time'] > 2 * max_time_research))]
    # df_result['research_time'] = df_result.apply(
    #     lambda x: min_time_research if (x['well type'] == 'vertical' and x['research_time'] < min_time_research) else x[
    #         'research_time'], axis=1)
    # df_result['research_time'] = df_result.apply(lambda x: 2 * min_time_research if (
    #         x['well type'] == 'horizontal' and x['research_time'] < 2 * min_time_research) else x['research_time'],
    #                                              axis=1)

    df_result['oil_loss'] = 0
    df_result['gas_loss'] = 0
    df_result['injection_loss'] = 0
    df_result['oil_loss'] = df_result.apply(
        lambda x: (x.oilRate + x.condRate) * x.research_time if (
                str(x.gasStatus) == 'газоконденсатная') else x.oilRate * x.research_time, axis=1)  # потери по нефти
    df_result['gas_loss'] = df_result.apply(lambda x: (x.injectivity_day * x.research_time) if (
            str(x.gasStatus) == 'газонагнетательная') else x.gasRate * x.research_time, axis=1)  # потери по газу
    df_result['injection_loss'] = df_result['injectivity'] * df_result['research_time']  # потери по закачке воды
    df_result['coverage_percentage'] = unary_union(list(df_result['AREA'].explode())).area / obj_square
    # процент скважин в опорной сети из скважин на объекте по каждому типу
    df_result['percent_prod_wells'] = 0
    if df_prod_wells.shape[0] != 0:
        df_result['percent_prod_wells'] = df_result[df_result['fond'] == 'ДОБ'].shape[0] / prod_count
    df_result['percent_piez_wells'] = 0
    if df_piez_wells.shape[0] != 0:
        df_result['percent_piez_wells'] = df_result[df_result['fond'] == 'ПЬЕЗ'].shape[0] / piez_count
    df_result['percent_inj_wells'] = 0
    if df_inj_wells.shape[0] != 0:
        df_result['percent_inj_wells'] = df_result[df_result['fond'] == 'НАГ'].shape[0] / inj_count

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
    :return: Возвращает два DataFrame, по которым распределены скважины в слепой зоне(каждая вторая)
    """
    logger.info("Separation invisible wells")
    df_invisible = gpd.GeoDataFrame(df_invisible, geometry='GEOMETRY')
    df_invisible['dist_from_0'] = list(map(lambda x: x.distance(df_invisible['GEOMETRY'].iloc[0]),
                                           df_invisible['GEOMETRY']))
    df_invisible.sort_values(by=['dist_from_0'], ascending=True)
    list_separation = list(set(df_invisible.wellName.explode().unique()))
    list_first_year = []

    for i in tqdm(range(0, len(list_separation), 2), "Separation", position=0, leave=True,
                  colour='white', ncols=80):
        list_first_year += [list_separation[i]]
    df_invisible.drop(['dist_from_0'], axis=1, inplace=True)

    return (df_invisible[df_invisible['wellName'].isin(list_first_year)],
            df_invisible[~df_invisible['wellName'].isin(list_first_year)])
