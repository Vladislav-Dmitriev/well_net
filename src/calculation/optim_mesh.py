import geopandas as gpd
import pandas as pd
from loguru import logger
from shapely.ops import unary_union, cascaded_union
from tqdm import tqdm
from .support_functions import get_time_coef, get_property
from .shapely_geometry import intersect_number, check_intersection_area, add_shapely_types


@logger.catch(level='DEBUG')
def calc_optim_mesh(df_prod_wells, df_piez_wells, df_inj_wells, df_proj_wells,
                    df_result, df_necessarily_wells, horizon, mean_rad, coeff, key,
                    obj_square, path_property, list_exception, dict_parameters, log_user):
    """
    Функция расчета оптимальной опорной сетки, включающая в себя все функции обработки отдельных типов скважин

    :param df_necessarily_wells: DataFrame скважин, обязательных для включения в ОС
    :param obj_square: площадь объекта по крайним скважинам с отступом на средний радиус исследования
    :param key: результирующего ключ словаря
    :param coeff: коэффиуиент кратного увеличения радиуса
    :param mean_rad: средний радиус первого ряда окружения по объекту
    :param horizon: текущий объект расчета
    :param df_result: результирующий DataFrame
    :param df_inj_wells: DataFrame нагнетательных скважин
    :param df_piez_wells: DataFrame пьезометрических скважин
    :param df_prod_wells: DataFrame добывающих скважин
    :param df_proj_wells: DataFrame проектных скважин
    :param dict_parameters: словарь с параметрами (коэффициенты на радиус, углы перекрытия и тд)
    :param list_exception: список исключаемых из расчета скважин
    "слепых" зон и скважин в них
    :param path_property: путь к файлу с параметрами
    средним радиусом в этом случае для построения области взаимодействия будет заданное максимальное расстояние
    :param log_user: сигнал логирования для передачи сообщения пользователю
    :return: Возвращается словарь с добавленным ключом по коэффициенту умножения радиуса охвата
    """
    # удаление исключенных скважин из DataFrame пьезометров и нагнетательных
    log_user.emit("Удаление из расчета исключенных скважин")
    df_piez_inj_exception = pd.concat([df_piez_wells[df_piez_wells['wellName'].isin(list_exception)],
                                       df_inj_wells[df_inj_wells['wellName'].isin(list_exception)]],
                                      axis=0, sort=False).reset_index(drop=True)
    df_piez_inj_exception['wellNet'] = 'В списке исключений'
    df_piez = df_piez_wells[~df_piez_wells['wellName'].isin(list_exception)]
    df_inj = df_inj_wells[~df_inj_wells['wellName'].isin(list_exception)]
    log_user.emit("Процесс построения опорной сети")
    df_result = core_optim_mesh(list_exception, path_property, dict_parameters['percent'], mean_rad, coeff,
                                horizon, obj_square, dict_parameters['min_research_time'],
                                dict_parameters['max_research_time'], dict_parameters['calc_option'],
                                dict_parameters['limit_research_time'], df_piez, df_prod_wells.copy(), df_inj,
                                df_result.copy(), df_necessarily_wells)

    df_result['year_of_survey'] = 0  # для скважин первой итерации расчета год исследования ставится текущий

    if ((coeff > dict_parameters['limit_radius_coef']) and (dict_parameters['separation_by_years'] is not None)
            and (dict_parameters['limit_radius_coef'] is not None)):
        df_result_invisible = pd.DataFrame()
        # выделение охваченных исследованиями добывающих скважин результата первой итерации расчета из исходного
        # DataFrame добывающих скважин
        df_prod_intersection = df_prod_wells[df_prod_wells['wellName'].isin(list(
            set(df_result['intersection'].explode().unique())))]

        list_invisible_wells = get_invisible_wells(df_result[~df_result['num_of_research']].copy(),
                                                   df_prod_intersection,
                                                   dict_parameters['percent'], mean_rad,
                                                   dict_parameters['limit_radius_coef'],
                                                   dict_parameters['calc_option'])  # список скважин в слепой зоне
        if list_invisible_wells:
            # выделение DataFrame добывающих скважин в слепых зонах из исходного DataFrame продуктивных
            log_user.emit("Выделение скважин для исследования в следующие года")
            df_prod_recalc = add_shapely_types(
                df_prod_intersection[df_prod_intersection['wellName'].isin(list_invisible_wells)],
                mean_rad, dict_parameters['limit_radius_coef'])
            # обновление столбца AREA с максимально допустимым R в DataFrame скважин, попавших на первую итерацию расчета
            df_piez_recalc = add_shapely_types(df_piez, mean_rad, dict_parameters['limit_radius_coef'])
            df_inj_recalc = add_shapely_types(df_inj, mean_rad, dict_parameters['limit_radius_coef'])
            log_user.emit("Процесс построения опорной сети на исследование в следующие года")
            df_result_invisible = core_optim_mesh(list_exception, path_property, dict_parameters['percent'], mean_rad,
                                                  coeff, horizon, obj_square, dict_parameters['min_research_time'],
                                                  dict_parameters['max_research_time'], dict_parameters['calc_option'],
                                                  dict_parameters['limit_research_time'], df_piez_recalc, df_prod_recalc,
                                                  df_inj_recalc, df_result_invisible,
                                                  pd.DataFrame(columns=df_piez_recalc.columns))

            if (dict_parameters['separation_by_years'] == 1) and (not df_result_invisible.empty):
                log_user.emit("Распределение скважин для исследования на 1 год вперед")
                df_result_invisible['year_of_survey'] = 1
                df_result = pd.concat([df_result, df_result_invisible],
                                      axis=0, sort=False).reset_index(drop=True)
            elif (dict_parameters['separation_by_years'] == 2) and (not df_result_invisible.empty):
                log_user.emit("Распределение скважин для исследования на 2 года вперед")
                df_first_year, df_second_year = separation_gdis(df_result_invisible)
                df_first_year['year_of_survey'], df_second_year['year_of_survey'] = 1, 2
                df_result = pd.concat([df_result, df_first_year, df_second_year],
                                      axis=0, sort=False).reset_index(drop=True)
            else:
                pass
        else:
            logger.info(f'Write to result dictionary by key {key}, there are not invisible wells')
            log_user.emit("Отсутствуют кандидаты для исследования в следующие года")

    # задание статуса по опорной сети
    df_result['wellNet'] = "Выбрана в опорную сеть"
    #  списки нагнетательных и пьезометрических скважин не вошедших в опорную сеть в ходе расчета
    list_inj_notwellnet = list(set(df_inj['wellName'].explode().unique()) - set(
        df_result.loc[df_result['fond'] == 'НАГ', 'wellName'].explode().unique()))
    list_piez_notwellnet = list(set(df_piez['wellName'].explode().unique()) - set(
        df_result.loc[df_result['fond'] == 'ПЬЕЗ', 'wellName'].explode().unique()))
    # список исследуемых добывающих скважин из столбца пересечений
    list_research_prod = list(set(df_result['intersection'].explode().unique()) -
                              set(df_result['wellName'].explode().unique()))
    # добавление в результирующий DataFrame исключенных скважин, скважин не выбранных в ОС и исследуемых
    df_result = pd.concat([df_result, df_piez_inj_exception, df_piez[df_piez['wellName'].isin(list_piez_notwellnet)],
                           df_inj[df_inj['wellName'].isin(list_inj_notwellnet)],
                           df_prod_wells[df_prod_wells['wellName'].isin(list_research_prod)]],
                          axis=0, sort=False).reset_index(drop=True)
    df_result.loc[df_result['wellName'].isin(list_piez_notwellnet + list_inj_notwellnet), 'wellNet'] =\
        'Исключена из опорной сети'
    df_result.loc[df_result['intersection'].map(str).str.contains('Не охвачена'), 'wellNet'] =\
        'Не охвачена исследованиями, исключена из ОС'
    df_result.loc[df_result['wellName'].isin(list_research_prod), 'wellNet'] = 'Охвачена исследованиями'

    # обнуление времени исследования пьезометрических скважин
    # df_result.loc[df_result['fond'] == 'ПЬЕЗ', 'research_time'] = 0

    # поиск охвата проектного фонда скважинами из ОС
    if not df_proj_wells.empty:
        list_proj_research = list(check_intersection_area(unary_union(list(df_result['AREA'].explode())),
                                                          df_proj_wells, dict_parameters['percent'],
                                                          dict_parameters['calc_option']))
        df_proj_wells.loc[df_proj_wells['wellName'].isin(list_proj_research), 'wellNet'] = 'Охвачена исследованиями'
        df_proj_wells.loc[df_proj_wells['wellNet'].isnull(), 'wellNet'] = 'Не охвачена исследованиями'
        df_result = pd.concat([df_result, df_proj_wells], axis=0, sort=False).reset_index(drop=True)

    df_result['current_horizon'] = horizon  # добавления столбца объектов для понимания, по какому идет расчет

    return df_result


@logger.catch(level='DEBUG')
def core_optim_mesh(list_prod_exception, path_property, percent, mean_rad, coeff, horizon,
                    obj_square, min_time_research, max_time_research, calc_option, limit_research_time,
                    df_piez_wells, df_prod_wells, df_inj_wells, df_result, df_necessarily_wells):
    """
    Функция для расчета результирующего DataFrame по объекту
    :param df_necessarily_wells: DataFrame с обязательными скважинами
    :param limit_research_time: параметр учета границ времени исследования
    :param calc_option: параметр определяет критерий учета процента длины ГС для попадания в зону охвата
    :param max_time_research: ограничение максимального времени исследования ННС
    :param min_time_research: ограничение минимального времени исследования ННС
    :param obj_square: площадь объекта месторождения по краевым скважинам
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
    inj_count = df_inj_wells.shape[0] + df_necessarily_wells[df_necessarily_wells['fond'] == 'НАГ'].shape[0]
    prod_count = df_prod_wells.shape[0] + df_necessarily_wells[df_necessarily_wells['fond'] == 'ДОБ'].shape[0]
    piez_count = df_piez_wells.shape[0] + df_necessarily_wells[df_necessarily_wells['fond'] == 'ПЬЕЗ'].shape[0]
    gas_prod_count = df_prod_wells[df_prod_wells['gasStatus'].str.contains('газ')].shape[0] + df_necessarily_wells[
        (df_necessarily_wells['fond'] == 'ДОБ') & (df_necessarily_wells['gasStatus'].str.contains('газ'))].shape[0]

    if df_prod_wells.shape[0] != 0:

        logger.info(f'Calculation for {horizon}')
        # I. Piezometric wells_____________________________________________________________________________________

        isolated_wells, df_piez_wells, hor_prod_wells, df_result = piez_calc(df_piez_wells, df_prod_wells.copy(),
                                                                             df_result, percent, calc_option)

        # II. Injection wells______________________________________________________________________________________
        if len(isolated_wells):
            isolated_wells, hor_prod_wells, df_inj_wells, df_result = inj_calc(isolated_wells, hor_prod_wells,
                                                                              df_inj_wells, df_result, percent,
                                                                              calc_option)

            # III. Single wells____________________________________________________________________________________
            if len(isolated_wells):
                single_wells, hor_prod_wells, df_result = single_calc(list_prod_exception, isolated_wells,
                                                                      hor_prod_wells, df_result, percent, calc_option)
    else:
        logger.info(f'THERE ARE NO PRODUCTION WELLS FOR OBJECT {horizon}')

    df_result = pd.concat([df_result, df_necessarily_wells], axis=0, sort=False).reset_index(drop=True)

    df_result['mean_radius'] = mean_rad * coeff  # столбец с текущим средним радиусом по объекту, домножается на коэфф.
    df_result['min_dist'] = df_result['min_dist'] * coeff
    # коэффициент для расчета времени исследования
    dict_property = get_property(path_property)
    df_result['time_coef/objects'] = df_result.apply(
        lambda x: get_time_coef(dict_property, x.workHorizon, x.water_cut, x.oilfield, x.gasStatus), axis=1)
    df_result['time_coef'] = list(map(lambda x: x[0], df_result['time_coef/objects']))
    # рассчитанные средние свойства по скважинам
    # df_result['mu'] = list(map(lambda x: x[1], df_result['time_coef/objects']))
    # df_result['ct'] = list(map(lambda x: x[2], df_result['time_coef/objects']))
    # df_result['phi'] = list(map(lambda x: x[3], df_result['time_coef/objects']))
    df_result['k'] = list(map(lambda x: x[4], df_result['time_coef/objects']))  # проницаемость
    df_result['gas_visc'] = list(map(lambda x: x[5], df_result['time_coef/objects']))  # вязкость газа в пл. условиях
    df_result['pressure'] = list(map(lambda x: x[6], df_result['time_coef/objects']))  # пл. давление атм
    df_result['default_count'] = list(map(lambda x: x[7], df_result['time_coef/objects']))  # кол-во объектов
    # со свойствами по умолчанию
    df_result['obj_count'] = list(map(lambda x: x[8], df_result['time_coef/objects']))
    df_result['percent_of_default'] = list(map(lambda x: 100 * x[7] / x[8], df_result['time_coef/objects']))  # процент
    # объектов со свойствами по умолчанию
    df_result.drop(['time_coef/objects'], axis=1, inplace=True)
    df_result['research_time'] = (df_result['min_dist'] * df_result['min_dist']
                                  * df_result['time_coef'])  # время исследования в сут через min расстояние

    # filter and delete wells, which don't fit the parameters limit research time
    if limit_research_time and (min_time_research != ''):
        df_result['research_time'] = df_result.apply(
            lambda x: min_time_research if (
                    x['well type'] == 'vertical' and x['research_time'] < min_time_research) else
            x['research_time'], axis=1)
        df_result['research_time'] = df_result.apply(lambda x:
                                                     2 * min_time_research if
                                                     (x['well type'] == 'horizontal' and x['research_time'] <
                                                      2 * min_time_research) else
                                                     x['research_time'], axis=1)

    if limit_research_time and (max_time_research != ''):
        df_result['research_time'] = df_result.apply(
            lambda x: max_time_research if (
                    x['well type'] == 'vertical' and x['research_time'] > max_time_research) else
            x['research_time'], axis=1)
        df_result['research_time'] = df_result.apply(
            lambda x: 2 * max_time_research if (
                    x['well type'] == 'horizontal' and x['research_time'] > 2 * max_time_research) else
            x['research_time'], axis=1)

    df_result['oil_loss'] = 0
    df_result['gas_loss'] = 0
    df_result['injection_loss'] = 0
    df_result['oil_loss'] = df_result.apply(
        lambda x: (x.oilRate + x.condRate) * x.research_time if (
                str(x.gasStatus) == 'газоконденсатная') else x.oilRate * x.research_time, axis=1)  # потери по нефти, т
    df_result['gas_loss'] = df_result.apply(lambda x: (x.injectivity_day * x.research_time) if (
            str(x.gasStatus) == 'газонагнетательная') else x.gasRate * x.research_time,
                                            axis=1)  # потери по газу, тыс.м3
    df_result['injection_loss'] = df_result['injectivity'] * df_result['research_time']  # потери по закачке воды, м3
    df_result['coverage_percentage'] = unary_union(list(df_result['AREA'].explode())).area / obj_square
    # процент скважин в опорной сети из скважин на объекте по каждому типу
    df_result['percent_piez_wells'] = 0
    if piez_count != 0:
        df_result['percent_piez_wells'] = 100 * df_result[(df_result['fond'] == 'ПЬЕЗ')].shape[0] / piez_count
    df_result['percent_inj_wells'] = 0
    if inj_count != 0:
        df_result['percent_inj_wells'] = 100 * df_result[(df_result['fond'] == 'НАГ')].shape[0] / inj_count
    df_result['percent_prod_wells'] = 0
    if prod_count != 0:
        df_result['percent_prod_wells'] = 100 * df_result[
            (df_result['fond'] == 'ДОБ') & (~df_result['intersection'].map(str).str.contains('Не охвачена'))].shape[
            0] / prod_count
    df_result['percent_gas_wells'] = 0
    if gas_prod_count != 0:
        df_result['percent_gas_wells'] = 100 * df_result[
            (df_result['fond'] == 'ДОБ') & (df_result['gasStatus'].str.contains('газ'))].shape[0] / gas_prod_count

    return df_result


@logger.catch(level='DEBUG')
def piez_calc(df_piez_wells, hor_prod_wells, df_result, percent, calc_option):
    """
    Функция обрабатывает DataFrame из пьезометров, подающийся на вход
    :param calc_option: параметр определяет критерий учета процента длины ГС для попадания в зону охвата
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
        hor_prod_wells, df_piez_wells = intersect_number(hor_prod_wells, df_piez_wells, percent, calc_option)

        # !!!OPTIMIZATION!!!
        list_piez_wells = optimization(hor_prod_wells, df_piez_wells)

        # final list of piezometers to df_result
        df_result = pd.concat([df_result, df_piez_wells[df_piez_wells.wellName.isin(list_piez_wells)]],
                              axis=0, sort=False).reset_index(drop=True)

        # wells without communication with piezometer
        isolated_wells = hor_prod_wells[hor_prod_wells.number == 0].wellName.values
        hor_prod_wells.drop(["intersection", "number"], axis=1, inplace=True)
    else:
        isolated_wells = hor_prod_wells.wellName.values
    return isolated_wells, df_piez_wells, hor_prod_wells, df_result


@logger.catch(level='DEBUG')
def inj_calc(isolated_wells, hor_prod_wells, df_inj_wells, df_result, percent, calc_option):
    """
    Функция обарабатывает DataFrame нагнетательных скважин
    :param calc_option: параметр определяет критерий учета процента длины ГС для попадания в зону охвата
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
        hor_prod_wells, df_inj_wells = intersect_number(hor_prod_wells, df_inj_wells, percent, calc_option)

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


@logger.catch(level='DEBUG')
def single_calc(list_exception, isolated_wells, hor_prod_wells, df_result, percent, calc_option):
    """
    Функция обарабатывает DataFrame одиночных скважин
    :param calc_option: параметр определяет критерий учета процента длины ГС для попадания в зону охвата
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
                                                                 percent, calc_option),
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
        df_exception['intersection'] = df_exception['intersection'].apply(lambda x: 'Не охвачена исследованиями')
        df_exception['number'] = df_exception['number'].apply(lambda x: 0)
        df = pd.concat([df, df_exception], axis=0, sort=False).reset_index(drop=True)

    # delete duplicates
    clean_wells = []
    clean_wells += list(set(df['wellName']).difference(set(df['intersection'].explode().unique())))
    df = df[df.wellName.isin(clean_wells)]

    df_result = pd.concat([df_result, df], axis=0, sort=False).reset_index(drop=True)

    return clean_wells, hor_prod_wells, df_result


@logger.catch(level='DEBUG')
def get_invisible_wells(df_recalc, df_prod, percent, radius, coeff, calc_option):
    """
    Функция получения скважин в слепой зоне при k > 1.5 (k*R)
    :param calc_option: параметр определяет критерий учета процента длины ГС для попадания в зону охвата
    :param coeff: коэффициент домножения радиуса
    :param df_recalc: копия результирующего DataFrame для выделения скважин в слепой зоне
    :param df_prod: DataFrame добывающих скважин
    :param percent: процент перекрытия зоной охвата, при котором скважина попадает в нее
    :param radius: максимальный радиус охвата в слепой зоне
    :return: возвращает список скважин для дообследования и DataFrame с обновленным столбцом пересечений
    """
    logger.info("Search invisible wells")
    # copy values from intersection column
    df_recalc['intersection_kR'] = df_recalc['intersection']
    df_recalc['intersection'] = 0
    df_recalc['AREA'] = 0
    df_recalc = add_shapely_types(df_recalc, radius, coeff)
    df_recalc['intersection'] = list(map(lambda x: check_intersection_area(x, df_prod, percent, calc_option),
                                         df_recalc.AREA))
    intersect_kR, intersect_R = (set(df_recalc['intersection_kR'].explode().unique()),
                                 set(df_recalc['intersection'].explode().unique()))
    intersect_kR = {x for x in intersect_kR if pd.notna(x)}
    intersect_R = {x for x in intersect_R if pd.notna(x)}
    list_invisible_wells = list(intersect_kR - intersect_R)

    return list_invisible_wells


@logger.catch(level='DEBUG')
def separation_gdis(df_invisible):
    """
    Функция разделения скважин в слепых зонах на 2 года
    :param df_invisible: DataFrame скважин, которые попали в слепую зону
    :return: Возвращает два DataFrame, по которым распределены скважины в слепой зоне(каждая вторая)
    """
    logger.info("Separation invisible wells")
    df_invisible = gpd.GeoDataFrame(df_invisible, geometry='GEOMETRY')
    # add column with distance from nearest well
    df_invisible['dist_from_0'] = list(map(lambda x: x.distance(df_invisible['GEOMETRY'].iloc[0]),
                                           df_invisible['GEOMETRY']))
    df_invisible = df_invisible.sort_values(by=['dist_from_0'], ascending=True)
    list_separation = list(set(df_invisible.wellName.explode().unique()))
    list_first_year = []
    # separate dataframe on two parts
    for i in tqdm(range(0, len(list_separation), 2), "Separation", position=0, leave=True,
                  colour='white', ncols=80, disable=True):
        list_first_year += [list_separation[i]]
    df_invisible.drop(['dist_from_0'], axis=1, inplace=True)

    return (df_invisible[df_invisible['wellName'].isin(list_first_year)],
            df_invisible[~df_invisible['wellName'].isin(list_first_year)])


@logger.catch(level='DEBUG')
def optimization(df_prod, df_inj_piez):
    """
    Выделяется список нагнетательных/пьезометров из DataFrame продуктивных,
    имеющих 1 пересечение. Оптимизация заключается в переопределении
    списка нагн/пьез. с помощью исключения скважин, входящих
    как в список пересечений, так и в список исключений, из df_optim
    :param df_prod: DataFrame добывающих скважин
    :param df_inj_piez: DataFrame нагнетательных/пьезометров
    :return: Возвращает обновленный список нагнетательных/пьезометров
    """
    list_inj_piez_wells = []
    # выделяем из столбца пересечений DataFrame продуктивных скважин строки, где добывающие охвачены только 1
    # пьезометром, и включаем эти пьезометры в список
    list_inj_piez_wells += list(df_prod[df_prod['number'] == 1]['intersection'].explode().unique())
    # по выделенному списку пьезометров из DataFrame пьезометрических скважин выделяем добывающие, которые охвачены ими
    list_prod_wells = df_inj_piez[
        df_inj_piez['wellName'].isin(list_inj_piez_wells)]['intersection'].explode().unique()
    # создаем dataframe оптимизации из DataFrame пьезометров, исключая те пьезометры, которые единственные охватывают
    # одну из добывающих скважин, их в любом случае включаем в опорную сеть
    df_optim = df_inj_piez[~df_inj_piez['wellName'].isin(list_inj_piez_wells)]
    # из столбца пересечений DataFrame оптимизации удаляются все добывающие, которые охвачены только 1 пьезометром
    df_optim.intersection = list(
        map(lambda x: list(set(x).difference(set(list_prod_wells))), df_optim['intersection']))
    # добавление столбца с кол-вом пересечений
    df_optim.number = list(map(lambda x: len(x), df_optim['intersection']))
    # отсеиваются одиночные скважины, не имеющие пересечений
    df_optim = df_optim[df_optim['number'] > 0]
    # в df_optim остались скважины с ненулевыми пересечениями
    if not df_optim.empty:
        #  создаем сет уникальных значений столбца с пересечениями и сортируем dataframe по кол-ву пересечений
        set_visible_wells = set(df_optim['intersection'].explode().unique())
        df_optim = df_optim.sort_values(by=['number'], ascending=True)
        # на каждой итерации создается сет охваченных скважин без текущей строки, если он совпадает полным сетом,
        # то текущая скважина удаляется, тк охваченные ею скважины есть в пересечениях других
        for well in df_optim.wellName.values:
            set_exception = set(df_optim[df_optim['wellName'] != well]['intersection'].explode().unique())
            # при совпадении наборов исключений и пересечений из df_optim исключается итерируемая скважина
            # и добавляется к списку нагн./пьез.
            if set_exception == set_visible_wells:
                df_optim = df_optim[df_optim.wellName != well]
        list_inj_piez_wells += list(df_optim.wellName.values)

    return list_inj_piez_wells
