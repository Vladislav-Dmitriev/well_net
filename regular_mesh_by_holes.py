from tqdm import tqdm

from FirstRowWells import mean_radius
from geometry import add_shapely_types


def calc_mesh_by_holes(df_input, dict_parameters):
    list_horizon = list(set(df_input.workHorizon.str.replace(" ", "").str.split(",").explode()))
    list_horizon.sort()
    # словарь для записи результатов
    dict_holes_result = {}

    for horizon in tqdm(list_horizon, "Calculation mesh by holes", position=0, leave=True,
                        colour='white', ncols=80):
        # отбираю скважины на объект
        df_horizon = df_input[
            list(map(lambda x: len(set(x.replace(" ", "").split(",")) & set([horizon])) > 0, df_input.workHorizon))]
        mean_rad, df_horizon = mean_radius(df_horizon, dict_parameters['verticalWellAngle'],
                                           dict_parameters['MaxOverlapPercent'],
                                           dict_parameters['angle_horizontalT1'],
                                           dict_parameters['angle_horizontalT3'], dict_parameters['max_distance'])

        for key, coeff in zip(dict_holes_result, dict_parameters['mult_coef']):
            df_horizon = add_shapely_types(df_horizon, mean_rad, coeff)
            # df_horizon = add_shapely_types(df_horizon, 2 * mean_rad, coeff)
            # df_horizon = add_shapely_types(df_horizon, 3 * mean_rad, coeff)
            list_hor_wells = df_horizon.wellName.values


def holes_alg_by_fond(df, list_hor_wells):
    list_fonds = list(set(df['fond'].explode().unique()))
