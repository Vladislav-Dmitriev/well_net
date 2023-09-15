import pandas as pd
from functions import (intersect_number, optimization, check_intersection_area,
                       unpack, add_shapely_types, get_time_research, get_time_coef)
from tqdm import tqdm
from mapping import visualisation
from FirstRowWells import mean_radius


def piez_calc(df_piez_wells, hor_prod_wells, df_result):
    '''
    Функция обрабатывает DataFrame из пьезометров, подающийся на вход
    :param df_piez_wells: DataFrame из пьезометров, выделенный из входного файла
    :param hor_prod_wells: DataFrame из добывающих скважин
    :param df_result: В функцию подается DataFrame df_result для добавления в общий результат расчета пьезометров
    :return: Возвращаются: 1) список скважин, не имеющих пересечений;
                           2) DataFrame пьезометров;
                           3) DataFrame добывающих;
                           4) Общий DataFrame со всеми результатами расчета по объекту
    '''
    if not df_piez_wells.empty:

        # check_intersection
        hor_prod_wells, df_piez_wells = intersect_number(hor_prod_wells, df_piez_wells)

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


def inj_calc(isolated_wells, hor_prod_wells, df_inj_wells, df_result):
    '''
    Функция обарабатывает DataFrame нагнетательных скважин
    :param isolated_wells: Список скважин, не имеюших пересечений
    :param hor_prod_wells: DataFrame добывающих скважин
    :param df_inj_wells: DataFrame нагнетательных скважин
    :param df_result: Результирующий DataFrame, к которому добавится результат обработки DataFrame нагнетательных скв.
    :return: Возвращаются: 1) список скважин, не имеющих пересечений;
                           2) DataFrame нагнетательных;
                           3) DataFrame добывающих;
                           4) Общий DataFrame со всеми результатами расчета по объекту
    '''
    hor_prod_wells = hor_prod_wells[hor_prod_wells.wellName.isin(isolated_wells)]

    if not df_inj_wells.empty:

        # check_intersection
        hor_prod_wells, df_inj_wells = intersect_number(hor_prod_wells, df_inj_wells)

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


def single_calc(isolated_wells, hor_prod_wells, df_result):
    '''
    Функция обарабатывает DataFrame одиночных скважин
    :param isolated_wells: Список скважин, не имеюших пересечений
    :param hor_prod_wells: DataFrame добывающих скважин
    :param df_result: Результирующий DataFrame, к которому добавится результат обработки DataFrame одиночных скв.
    :return: Возвращаются: 1) список скважин, не имеющих пересечений;
                           2) DataFrame добывающих;
                           3) Общий DataFrame со всеми результатами расчета по объекту
    '''
    single_wells = []
    hor_prod_wells = hor_prod_wells[hor_prod_wells.wellName.isin(isolated_wells)]

    # check_intersection
    hor_prod_wells.insert(loc=hor_prod_wells.shape[1], column="intersection",
                          value=list(map(lambda x, y:
                                         check_intersection_area(x, hor_prod_wells
                                         [hor_prod_wells.wellName != y]),
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


def calc_contour(df_input, polygon, contour_name, max_distance, path_property, **dict_constant):
    '''
    Функция для расчета скважин, включающая в себя все функции расчета отдельных типов скважин
    :param path_property: путь к файлу с параметрами
    :param df_input: DataFrame, полученные из исходного файла со свкажинами
    :param polygon: Геометрический объект GeoPandas, полученный из координат контура, подающегося в программу
    :param max_distance: в случае, когда скважины находятся друг от друга на расстоянии больше максимального,
    средним радиусом в этом случае для построения области взаимодействия будет заданное максимальное расстояние
    :param contour_name: Название файла с координатами текущего контура без расширения файла
    :param dict_constant: Словарь с характером работы и состоянием скажины
    :return: Возвращается общий DataFrame с результатами расчета по всем объектам и DataFrame с добывающими скважинами
    '''

    PROD_STATUS, PROD_MARKER, PIEZ_STATUS, INJ_MARKER, INJ_STATUS = unpack(dict_constant)
    list_objects = df_input.workHorizon.str.replace(" ", "").str.split(",").explode().unique()
    list_objects.sort()

    df_result_all = pd.DataFrame()
    for horizon in tqdm(list_objects, "calculation for objects"):
        df_result = pd.DataFrame()
        # для каждого объекта определяется свой df_horizon_input
        df_horizon_input = df_input[list(map(lambda x: len(set(x.replace(" ", "").split(",")) & set([horizon])) > 0,
                                             df_input.workHorizon))]
        mean_rad = mean_radius(df_horizon_input, 10, 30,
                               10, 10, max_distance)
        df_horizon_input = add_shapely_types(df_horizon_input, mean_rad)
        df_prod_wells = df_horizon_input.loc[(df_horizon_input.workMarker == PROD_MARKER)
                                             & (df_horizon_input.wellStatus.isin(PROD_STATUS))]
        df_piez_wells = df_horizon_input.loc[df_horizon_input.wellStatus == PIEZ_STATUS]
        df_inj_wells = df_horizon_input.loc[(df_horizon_input.workMarker == INJ_MARKER)
                                            & (df_horizon_input.wellStatus.isin(INJ_STATUS))]
        if df_prod_wells.empty:
            continue

        # I. Piezometric wells__________________________________________________________________________________________

        isolated_wells, df_piez_wells, hor_prod_wells, df_result = piez_calc(df_piez_wells,
                                                                             df_prod_wells.copy(),
                                                                             df_result)

        # II. Injection wells___________________________________________________________________________________________
        if len(isolated_wells):
            isolated_wells, hor_prod_wells, df_inj_wells, df_result = inj_calc(isolated_wells,
                                                                               hor_prod_wells,
                                                                               df_inj_wells,
                                                                               df_result)

            # III. Single wells_________________________________________________________________________________________
            if len(isolated_wells):
                single_wells, hor_prod_wells, df_result = single_calc(isolated_wells,
                                                                      hor_prod_wells,
                                                                      df_result)
        # MAP drawing_______________________________________________________________________________________________
        visualisation(polygon, contour_name, horizon, mean_rad, df_result, df_prod_wells, **dict_constant)
        df_result.insert(loc=df_result.shape[1], column="mean_radius", value=mean_rad)
        # добавление столбца со временем исследования
        # df_result = get_time_research(path_property, df_result, horizon)
        df_result['time_coef'] = df_result['workHorizon'].apply(lambda x: get_time_coef(path_property, x,
                                                     'mu', 'ct', 'phi', 'k'))
        df_result['research_time'] = df_result['mean_radius']*df_result['time_coef']
        df_result_all = pd.concat([df_result_all, df_result],
                                  axis=0, sort=False).reset_index(drop=True)


    return df_result_all
