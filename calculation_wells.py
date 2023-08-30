import pandas as pd
from functions import intersect_number, optimization, check_intersection_area

def piez_calc(horizon, df_piez_wells, hor_prod_wells, df_result):
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

def single_calc(horizon, isolated_wells, hor_prod_wells, df_result):
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
        while (len(list_wells) != 0):
            single_wells += [list_wells[0]]
            list_exeption = [list_wells[0]] + \
                            list(df_optim[df_optim.wellNumberColumn == list_wells[0]].intersection.explode().unique())
            list_wells = [x for x in list_wells if x not in list_exeption]

        # final list of injection to result_df
    df_result = pd.concat(
        [df_result, hor_prod_wells[hor_prod_wells.wellNumberColumn.isin(single_wells)]],
        axis=0, sort=False).reset_index(drop=True)
    # dict_result[horizon] = df_result

    return single_wells, hor_prod_wells, df_optim, df_result

def calc_without_contour(horizon, df_prod_wells, df_piez_wells, df_inj_wells, df_result, df_result_all):

    hor_prod_wells = df_prod_wells[list(map(lambda x: len(set(x.replace(" ", "").split(",")) & set[horizon]) > 0,
                                            df_prod_wells.workHorizon))]
    # I. Piezometric wells__________________________________________________________________________________________

    isolated_wells, hor_piez_wells, hor_prod_wells, df_result = piez_calc(horizon, df_piez_wells,
                                                                          hor_prod_wells,
                                                                          df_result)
    df_result_all = pd.concat([df_result_all, df_result], axis=0, sort=False).reset_index(drop=True)

    # II. Injection wells___________________________________________________________________________________________
    if len(isolated_wells):
        isolated_wells, hor_prod_wells, df_inj_wells, df_result = inj_calc(horizon, isolated_wells,
                                                                           hor_prod_wells,
                                                                           df_inj_wells,
                                                                           df_result)

        # III. Single wells_________________________________________________________________________________________
        if len(isolated_wells):
            single_wells, hor_prod_wells, df_optim, df_result, dict_result = single_calc(horizon,
                                                                                         isolated_wells,
                                                                                         hor_prod_wells,
                                                                                         df_result)
        else:
            df_result_all = pd.concat([df_result_all, df_result], axis=0, sort=False).reset_index(drop=True)
            df_result_all.drop_duplicates(subset=['wellNumberColumn'])
            # continue
    else:
        df_result_all = pd.concat([df_result_all, df_result], axis=0, sort=False).reset_index(drop=True)
        df_result_all.drop_duplicates(subset=['wellNumberColumn'])
        # continue
    df_result_all.drop_duplicates(subset=['wellNumberColumn'])
    return df_result_all

