import pandas as pd
from loguru import logger
from shapely.ops import unary_union
from tqdm import tqdm
from .check_first_row_wells import mean_radius
from .support_functions import dict_keys
from .shapely_geometry import add_shapely_types
from .regular_mesh import calc_regular_mesh
from .optim_mesh import calc_optim_mesh
from src.input_output.preparing_data import fonds_for_calc


@logger.catch(level='DEBUG')
def calculation(polygon, df_in_contour, contour_name, path_property, list_exception,
                dict_parameters, log_user, progress_bar):
    """
    Основная функция расчета
    :param polygon: контур, заданный пользователем
    :param df_in_contour: DataFrame из скважин, находящихся внутри контура
    :param contour_name: имя контура
    :param path_property: путь к справочнику с PVT свойствами
    :param list_exception: список исключаемых скважин
    :param dict_parameters: словарь с параметрами расчета
    :param log_user:
    :param progress_bar:
    :return: словарь с результирующим DataFrame по каждому ключу
    """

    if dict_parameters['mult_coef'] is None:
        logger.info('List of radius multiples is not specified. Current coefficient is 1.')
        dict_parameters['mult_coef'] = [1]
    dict_result = dict_keys(dict_parameters['mult_coef'], contour_name)
    list_objects = list(set(df_in_contour.workHorizon.str.replace(" ", "").str.split(",").explode()))
    list_objects.sort()

    for horizon in tqdm(list_objects, "Calculation for objects", position=0, leave=True,
                        colour='white', ncols=80, disable=True):
        logger.info(f'Current horizon: {horizon}')
        log_user.emit(f"-----Построение опорной сетки по объекту {horizon}")
        # для каждого объекта определяется свой df_horizon
        df_horizon = df_in_contour[
            list(map(lambda x: len(set(x.replace(" ", "").split(",")) & set([horizon])) > 0,
                     df_in_contour.workHorizon))]
        # условие на пропуск итерации, если все скважины текущего объекта в контуре - проектные
        if df_horizon[df_horizon['fond'] != 'ПРОЕКТ'].empty:
            log_user.emit("На текущем объекте расчета нет скважин, кроме проектных. Итерация пропускается")
            continue
        df_proj_wells = df_horizon[df_horizon['fond'] == 'ПРОЕКТ']
        log_user.emit("Расчет среднего расстояния среди скважин первого ряда окружения")
        # расчет среднего и минимального радиуса первого окружения по объекту
        mean_rad, df_horizon = mean_radius(df_horizon[df_horizon['fond'] != 'ПРОЕКТ'],
                                           dict_parameters['verticalWellAngle'],
                                           dict_parameters['MaxOverlapPercent'],
                                           dict_parameters['angle_horizontalT1'],
                                           dict_parameters['angle_horizontalT3'],
                                           dict_parameters['max_distance'], progress_bar)
        logger.info(f'Research radius for horizon {horizon} calculated: {mean_rad}')
        log_user.emit(f"-----Применение заданных коэффициентов на средний радиус исследования")
        total_count_coef = len(dict_parameters['mult_coef'])
        for i, (key, coeff) in enumerate(zip(dict_result, dict_parameters['mult_coef'])):
            # площадь многоугольника построенного по крайним скважинам, попавшим на расчет
            obj_square = unary_union(list(df_horizon[df_horizon['fond'] != 'ПРОЕКТ']['GEOMETRY'].explode())).convex_hull
            obj_square = obj_square.buffer(
                mean_rad * coeff).area  # площадь охватывающая все скважины объекта, попавшие на расчет
            logger.info(f'Add shapely types with coefficient = {coeff}')
            df_horizon = add_shapely_types(df_horizon, mean_rad, coeff)
            logger.info(f'Key of dictionary: {key}, Mult coefficient: {coeff}')
            df_result = pd.DataFrame()
            # сценарий с целью охвата всех добывающих
            if dict_parameters['calculation_scenario'] == 'optimize':
                logger.info(f'Selected optimize mesh scenario')
                log_user.emit(f"Вычисление по оптимальному сценарию с коэффициентом {coeff}")
                df_prod_wells, df_piez_wells, df_inj_wells, df_necessarily_wells, df_exception_calc, mean_oilrate =\
                    fonds_for_calc(df_horizon.copy(), 'optimize', dict_parameters['percent'],
                                   dict_parameters['calc_option'], dict_parameters['mean_oilrate_option'],
                                   dict_parameters['percent_oilrate'])
                # если DataFrame с добывающими скважинами и DataFrame с приоритетными скважинами пустые,
                # то вычисления по объекту нет
                if (df_prod_wells.shape[0] + df_necessarily_wells.shape[0]) == 0:
                    logger.info(f'THERE ARE NO PRODUCTION AND NECESSARILY WELLS FOR OBJECT {horizon}')
                    log_user.emit(f"")
                    continue
                df_result = calc_optim_mesh(df_prod_wells, df_piez_wells, df_inj_wells, df_proj_wells, df_result,
                                            df_necessarily_wells, horizon, mean_rad, coeff, key, obj_square,
                                            path_property,
                                            list_exception, dict_parameters, log_user)
            # сценарий с построением регулярной сеткой на каждом из фондов
            elif dict_parameters['calculation_scenario'] == 'regular':
                logger.info(f'Selected regular mesh scenario')
                log_user.emit(f"Вычисление по сценарию регулярной сетки с коэффициентом {coeff}")
                df_prod_wells, df_piez_wells, df_inj_wells, df_necessarily_wells, df_exception_calc, mean_oilrate = \
                    fonds_for_calc(df_horizon.copy(), 'regular', dict_parameters['percent'],
                                   dict_parameters['calc_option'], dict_parameters['mean_oilrate_option'],
                                   dict_parameters['percent_oilrate'])
                df_result = calc_regular_mesh(df_prod_wells, df_piez_wells, df_inj_wells, df_proj_wells, df_result,
                                              df_necessarily_wells, horizon, path_property, dict_parameters, obj_square,
                                              mean_rad, coeff, list_exception, log_user)

            else:
                raise NameError(
                    f'Wrong marker name: {dict_parameters["calculation_scenario"]}. Check parameters.yml file')
            # добавление скважин, не попавших на расчет(исключены по среднему дебиту объекта или охвачены приоритетными)
            df_exception_calc['current_horizon'] = horizon
            df_result = pd.concat([df_result, df_exception_calc], axis=0, sort=False).reset_index(drop=True)
            df_result['mean_oilrate'] = mean_oilrate
            df_result['limit_oilrate'] = dict_parameters['limit_oilrate']
            logger.info(f'Write to result dictionary by key {key}')
            dict_result[key] = [pd.concat([dict_result[key][0], df_result],
                                          axis=0, sort=False).reset_index(drop=True), polygon]
            progress_bar.emit(int((i + 1) / total_count_coef * 100))

    return dict_result
