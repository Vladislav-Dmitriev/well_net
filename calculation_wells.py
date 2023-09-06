import pandas as pd
from functions import intersect_number, optimization, check_intersection_area, unpack
from tqdm import tqdm
from mapping import visualisation


def piez_calc(horizon, df_piez_wells, hor_prod_wells, df_result):
    '''
    Функция обрабатывает DataFrame из пьезометров, подающийся на вход
    :param horizon: объект, по которому идет расчет
    :param df_piez_wells: DataFrame из пьезометров, выделенный из входного файла
    :param hor_prod_wells: DataFrame из добывающих скважин
    :param df_result: В функцию подается DataFrame df_result для добавления в общий результат расчета пьезометров
    :return: Возвращаются: 1) список скважин, не имеющих пересечений;
                           2) DataFrame пьезометров;
                           3) DataFrame добывающих;
                           4) Общий DataFrame со всеми результатами расчета по объекту
    '''
    hor_piez_wells = df_piez_wells[list(map(lambda x: len(set(x.replace(" ", "").split(",")) & set([horizon])) > 0,
                                            df_piez_wells.workHorizon))]

    if not hor_piez_wells.empty:

        # check_intersection
        hor_prod_wells, hor_piez_wells = intersect_number(hor_prod_wells, hor_piez_wells)

        # !!!OPTIMIZATION!!!
        list_piez_wells = optimization(hor_prod_wells, hor_piez_wells)

        # final list of piezometers to result_df
        df_result = pd.concat([df_result, hor_piez_wells[hor_piez_wells.wellNumberColumn.isin(list_piez_wells)]],
                              axis=0, sort=False).reset_index(drop=True)

        # wells without communication with piezometer
        isolated_wells = hor_prod_wells[hor_prod_wells.number == 0].wellNumberColumn.values
        hor_prod_wells.drop(["intersection", "number"], axis=1, inplace=True)
    else:
        isolated_wells = hor_prod_wells.wellNumberColumn.values
    return isolated_wells, hor_piez_wells, hor_prod_wells, df_result


def inj_calc(horizon, isolated_wells, hor_prod_wells, df_inj_wells, df_result):
    '''
    Функция обарабатывает DataFrame нагнетательных скважин
    :param horizon: Объект, по которому идет расчет
    :param isolated_wells: Список скважин, не имеюших пересечений
    :param hor_prod_wells: DataFrame добывающих скважин
    :param df_inj_wells: DataFrame нагнетательных скважин
    :param df_result: Результирующий DataFrame, к которому добавится результат обработки DataFrame нагнетательных скв.
    :return: Возвращаются: 1) список скважин, не имеющих пересечений;
                           2) DataFrame нагнетательных;
                           3) DataFrame добывающих;
                           4) Общий DataFrame со всеми результатами расчета по объекту
    '''
    hor_prod_wells = hor_prod_wells[hor_prod_wells.wellNumberColumn.isin(isolated_wells)]

    hor_inj_wells = df_inj_wells[
        list(map(lambda x: len(set(x.replace(" ", "").split(",")) & set([horizon])) > 0,
                 df_inj_wells.workHorizon))]

    if not hor_inj_wells.empty:

        # check_intersection
        hor_prod_wells, hor_inj_wells = intersect_number(hor_prod_wells, hor_inj_wells)

        # !!!OPTIMIZATION!!!
        list_inj_wells = optimization(hor_prod_wells, hor_inj_wells)

        # final list of injection to result_df
        df_result = pd.concat([df_result, hor_inj_wells[hor_inj_wells.wellNumberColumn.isin(list_inj_wells)]],
            axis=0, sort=False).reset_index(drop=True)

        # wells without communication with injection wells
        isolated_wells = hor_prod_wells[hor_prod_wells.number == 0].wellNumberColumn.values

        hor_prod_wells.drop(["intersection", "number"], axis=1, inplace=True)
    else:
        isolated_wells = hor_prod_wells.wellNumberColumn.values

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
    hor_prod_wells = hor_prod_wells[hor_prod_wells.wellNumberColumn.isin(isolated_wells)]

    # check_intersection
    hor_prod_wells.insert(loc=hor_prod_wells.shape[1], column="intersection",
                          value=list(map(lambda x, y:
                                         check_intersection_area(x, hor_prod_wells
                                         [hor_prod_wells.wellNumberColumn != y]),
                                         hor_prod_wells.AREA, hor_prod_wells.wellNumberColumn)))
    hor_prod_wells.insert(loc=hor_prod_wells.shape[1], column="number",
                          value=list(map(lambda x: len(x), hor_prod_wells.intersection)))

    single_wells += list(hor_prod_wells[hor_prod_wells.number == 0].wellNumberColumn)

    df_optim = hor_prod_wells[hor_prod_wells.number > 0]

    # !!!OPTIMIZATION!!!
    if not df_optim.empty:
        df_optim = df_optim.sort_values(by=['oilRate'], ascending=True)
        list_wells = df_optim.wellNumberColumn.values
        while len(list_wells) != 0:
            single_wells += [list_wells[0]]
            list_exeption = [list_wells[0]] + \
                            list(df_optim[df_optim.wellNumberColumn == list_wells[0]].intersection.explode().unique())
            list_wells = [x for x in list_wells if x not in list_exeption]

        # final list of injection to result_df
    df_result = pd.concat(
        [df_result, hor_prod_wells[hor_prod_wells.wellNumberColumn.isin(single_wells)]],
        axis=0, sort=False).reset_index(drop=True)

    return single_wells, hor_prod_wells, df_result


def calc_contour(df_input, polygon, contour_name, **dict_constant):
    '''
    Функция для расчета всех типов скважин, включающая в себя все функции расчета отдельных типов скважин
    :param df_input: DataFrame, полученны из исходного файла со свкажинами
    :param polygon: Геометрический объект GeoPandas, полученный из координат контура, подающегося в программу
    :param contour_name: Название файла с координатами текущего контура без расширения файла
    :param dict_constant: Словарь с характером работы и состоянием скажины
    :return: Возвращается общий DataFrame с результатами расчета по всем объектам и DataFrame с добывающими скважинами
    '''
    PROD_STATUS, PROD_MARKER, PIEZ_STATUS, INJ_MARKER, INJ_STATUS = unpack(dict_constant)
    df_prod_wells = df_input.loc[(df_input.workMarker == PROD_MARKER) & (df_input.wellStatus.isin(PROD_STATUS))]
    df_piez_wells = df_input.loc[df_input.wellStatus == PIEZ_STATUS]
    df_inj_wells = df_input.loc[(df_input.workMarker == INJ_MARKER) & (df_input.wellStatus.isin(INJ_STATUS))]
    list_objects = df_input.workHorizon.str.replace(" ", "").str.split(",").explode().unique()
    list_objects.sort()

    df_result_all = pd.DataFrame()
    for horizon in tqdm(list_objects, "calculation for objects"):
        df_result = pd.DataFrame()

        hor_prod_wells_first = df_prod_wells[list(map(lambda x: len(set(x.replace(" ", "").split(",")) &
                                                                    set([horizon])) > 0, df_prod_wells.workHorizon))]
        if hor_prod_wells_first.empty:
            continue

        # I. Piezometric wells__________________________________________________________________________________________

        isolated_wells, hor_piez_wells, hor_prod_wells, df_result = piez_calc(horizon, df_piez_wells,
                                                                              hor_prod_wells_first,
                                                                              df_result)

        # II. Injection wells___________________________________________________________________________________________
        if len(isolated_wells):
            isolated_wells, hor_prod_wells, df_inj_wells, df_result = inj_calc(horizon, isolated_wells,
                                                                               hor_prod_wells,
                                                                               df_inj_wells,
                                                                               df_result)

            # III. Single wells_________________________________________________________________________________________
            if len(isolated_wells):
                single_wells, hor_prod_wells, df_result = single_calc(isolated_wells,
                                                                                hor_prod_wells,
                                                                                     df_result)
        # MAP drawing_______________________________________________________________________________________________
        visualisation(polygon, contour_name, horizon, df_result, hor_prod_wells_first, **dict_constant)
        df_result_all = pd.concat([df_result_all, df_result],
            axis=0, sort=False).reset_index(drop=True)

    return df_result_all, df_prod_wells

