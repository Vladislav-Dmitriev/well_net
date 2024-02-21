import pandas as pd
from loguru import logger
from tqdm import tqdm

from FirstRowWells import mean_radius
from geometry import add_shapely_types, check_intersection_area
from wells_clustering import dict_mesh_keys


def calc_mesh_by_holes(df_input, dict_parameters, contour_name):
    list_horizon = list(set(df_input.workHorizon.str.replace(" ", "").str.split(",").explode()))
    list_horizon.sort()
    # словарь для записи результатов
    dict_holes_result = dict_mesh_keys(dict_parameters['mult_coef'], contour_name)
    for horizon in tqdm(list_horizon, "Calculation mesh by holes", position=0, leave=True,
                        colour='white', ncols=80):
        logger.info(f'Current horizon: {horizon}')
        # отбираю скважины на объект
        df_horizon = df_input[
            list(map(lambda x: len(set(x.replace(" ", "").split(",")) & set([horizon])) > 0, df_input.workHorizon))]
        mean_rad, df_horizon = mean_radius(df_horizon, dict_parameters['verticalWellAngle'],
                                           dict_parameters['MaxOverlapPercent'],
                                           dict_parameters['angle_horizontalT1'],
                                           dict_parameters['angle_horizontalT3'], dict_parameters['max_distance'])
        df_horizon['current_horizon'] = horizon
        for key, coeff in zip(dict_holes_result, dict_parameters['mult_coef']):
            logger.info(f'Calculate by key {key} with coefficient {coeff}')
            df_horizon = add_shapely_types(df_horizon, mean_rad, coeff)
            df_result = holes_calc_fond(df_horizon, dict_parameters, mean_rad, coeff)
            dict_holes_result[key] = pd.concat([dict_holes_result[key], df_result], axis=0, sort=False).reset_index(
                drop=True)
    return dict_holes_result


def holes_calc_fond(df_horizon, dict_parameters, mean_rad, coeff):
    """

    :param df_horizon:
    :param dict_parameters:
    :param mean_rad:
    :param coeff:
    :return:
    """
    df_result = pd.DataFrame()
    list_fonds = list(set(df_horizon['fond'].explode().unique()))
    list_fonds.sort()

    for fond in tqdm(list_fonds, "Holes algorithm for fond", position=0, leave=True,
                     colour='white', ncols=80):
        # выделение скважин для текущего фонда итерации
        df_fond = df_horizon[df_horizon['fond'] == fond]
        df_fond['R'] = add_shapely_types(df_fond, mean_rad, coeff)['AREA']
        df_fond['2R'] = add_shapely_types(df_fond, 2 * mean_rad, coeff)['AREA']
        df_fond['3R'] = add_shapely_types(df_fond, 3 * mean_rad, coeff)['AREA']

        list_fond_wells = list(df_fond['wellName'].explode().unique())
        list_basic_wells = []
        while len(list_fond_wells) != 0:
            # выбор первой скважины DataFrame
            df_first_well = find_first_well(df_fond)
            df_first_well['intersection_r'] = list(
                map(lambda x, y: check_intersection_area(x, df_fond[df_fond['wellName'] != y],
                                                         dict_parameters['percent'], True),
                    df_first_well['R'], df_first_well['wellName']))
            list_R = list(set(df_first_well['intersection_r'].iloc[0]))
            if len(list_R) == 0:
                list_basic_wells += [df_first_well['wellName'].iloc[0]]
                list_fond_wells = [x for x in list_fond_wells if x != df_first_well['wellName'].iloc[0]]
                # переопределение DataFrame на фонд
                df_fond = df_fond[df_fond['wellName'].isin(list_fond_wells)]
                continue
            list_basic_wells += [df_first_well['wellName'].iloc[0]]
            list_fond_wells = [x for x in list_fond_wells if x not in list_R + [df_first_well['wellName'].iloc[0]]]
            df_fond = df_fond[df_fond['wellName'].isin(list_fond_wells)]
            df_first_well['intersection_2r'] = list(
                map(lambda x, y: check_intersection_area(x, df_fond[df_fond['wellName'] != y],
                                                         dict_parameters['percent'], True),
                    df_first_well['2R'], df_first_well['wellName']))
            list_2R = list(
                set(df_first_well['intersection_2r'].iloc[0]) - set(df_first_well['intersection_r'].iloc[0]))

            df_first_well['intersection_3r'] = list(
                map(lambda x, y: check_intersection_area(x, df_fond[df_fond['wellName'] != y],
                                                         dict_parameters['percent'], True),
                    df_first_well['3R'], df_first_well['wellName']))
            list_3R = list(
                set(df_first_well['intersection_3r'].iloc[0]) - set(df_first_well['intersection_2r'].iloc[0]))
            df_3R = df_fond[df_fond['wellName'].isin(list_3R)]
            # идет расчет по зоне 3R, причем изначально рассматриваются скважины, расположенные ближе к полигону 2R
            if not df_3R.empty:
                df_3R['distance'] = df_3R.apply(lambda x: x['GEOMETRY'].distance(df_first_well['2R'].iloc[0]), axis=1)
                df_3R = df_3R.sort_values(by=['distance'], axis=0, ascending=True)
                # в процессе расчета удаляются охваченные скважины из list_2R
                df_3R['intersection'] = list(
                    map(lambda x, y: check_intersection_area(x, df_fond[df_fond['wellName'] != y],
                                                             dict_parameters['percent'], True), df_3R['R'],
                        df_3R['wellName']))
                list_3R = list(df_3R['wellName'].explode())
                while not df_3R.empty:
                    current_well = list_3R[0]
                    list_exception = list(set(df_3R[df_3R['wellName'] == current_well]['intersection'].iloc[0])) + [
                        current_well]
                    list_fond_wells = [x for x in list_fond_wells if x not in list_exception]
                    list_3R = [x for x in list_3R if x not in list_exception]
                    list_2R = [x for x in list_2R if x not in list_exception]

                    list_basic_wells += [current_well]
                    df_3R = df_3R[df_3R['wellName'].isin(list_3R)]
            # переопределение DataFrame на фонд
            df_fond = df_fond[df_fond['wellName'].isin(list_fond_wells)]
            # создается DataFrame из фонда, содержащий скважины из list_2R. Если list_2R пустой, то есть условие
            df_2R = df_fond[df_fond['wellName'].isin(list_2R)]
            if not df_2R.empty:
                df_2R['distance'] = df_2R.apply(
                    lambda x: x['GEOMETRY'].distance(df_first_well['2R'].iloc[0].boundary), axis=1)
                df_2R = df_2R.sort_values(by=['distance'], axis=0, ascending=True)
                df_2R['intersection'] = list(
                    map(lambda x, y: check_intersection_area(x, df_fond[df_fond['wellName'] != y],
                                                             dict_parameters['percent'], True), df_2R['R'],
                        df_2R['wellName']))
                list_2R = list(df_2R['wellName'].explode())
                while not df_2R.empty:
                    current_well = list_2R[0]
                    list_exception = list(set(df_2R[df_2R['wellName'] == current_well]['intersection'].iloc[0])) + [
                        current_well]
                    list_fond_wells = [x for x in list_fond_wells if x not in list_exception]
                    list_2R = [x for x in list_2R if x not in list_exception]
                    list_basic_wells += [current_well]
                    df_2R = df_2R[df_2R['wellName'].isin(list_2R)]
                    # переопределение DataFrame на фонд
                df_fond = df_fond[df_fond['wellName'].isin(list_fond_wells)]
        df_result = pd.concat([df_result, df_horizon[df_horizon['wellName'].isin(list_basic_wells)]], axis=0,
                              sort=False).reset_index(drop=True)
    return df_result


def find_first_well(df):
    """

    :param df:
    :return:
    """
    min_y = df[['coordinateY', 'coordinateY3']].values.min()
    if df[(df['coordinateY'] == min_y) | (df['coordinateY3'] == min_y)].shape[0] != 1:
        df = df[(df['coordinateY'] == min_y) | (df['coordinateY3'] == min_y)]
        min_x = df[['coordinateX', 'coordinateX3']].values.min()
        df = df[(df['coordinateX'] == min_x) | (df['coordinateX3'] == min_x)]
        first_well = df[df['wellName'] == df['wellName'].iloc[0]]
        return first_well
    else:
        first_well = df[(df['coordinateY'] == min_y) | (df['coordinateY3'] == min_y)]
        return first_well
