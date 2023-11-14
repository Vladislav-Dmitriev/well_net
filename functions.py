import json
import os
import sys

import yaml


def unpack_status(dict_constant):
    """
    Распаковка параметров из словаря, для удобства использования в коде
    :param dict_constant: словарь со статусами скважин и характером их работы
    :return: возвращает статусы и характер работы скважин как отдельные переменные типа string
    """
    return dict_constant.get("PROD_STATUS"), dict_constant.get("PROD_MARKER"), dict_constant.get("PIEZ_STATUS"), \
        dict_constant.get("INJ_MARKER"), dict_constant.get("INJ_STATUS")


def get_time_research(path, df_result, horizon):
    """
    Добавление в результирующий DataFrame столбца со временем исследования, при условии,
    что дебит у скважины не 0
    :param path: путь к yaml-файлу с параметрами
    :param df_result: DataFrame рассчитанный для контура
    :param horizon: имя контура
    :return: возвращает DataFrame с добавленным столбцом времени исследования
    """
    dict_property = get_property(path)
    df_result.insert(loc=df_result.shape[1], column="research_time", value=0)
    df_result["research_time"] = df_result["research_time"].where((df_result["well type"] != "vertical") |
                                                                  (df_result["oilRate"] == 0),
                                                                  list(map(lambda x:
                                                                           462.2824 * x * dict_property[horizon]['mu'] *
                                                                           dict_property[horizon]['ct'] *
                                                                           dict_property[horizon]['phi'] /
                                                                           dict_property[horizon]['k'],
                                                                           df_result.mean_radius)))
    df_result["research_time"] = df_result["research_time"].where((df_result["well type"] != "horizontal") |
                                                                  (df_result["oilRate"] == 0),
                                                                  list(map(lambda x:
                                                                           462.2824 * x * dict_property[horizon]['mu'] *
                                                                           dict_property[horizon]['ct'] *
                                                                           dict_property[horizon]['phi'] /
                                                                           dict_property[horizon]['k'],
                                                                           df_result.mean_radius)))
    return df_result


def get_property(path):
    """
    Считывание параметров из yaml-файла в словарь
    :param path: путь к файлу с параметрами
    :return: возвращает словарь с параметрами по ключу объекта
    """
    with open(path, encoding='UTF-8') as json_file:
        reservoir_properties = json.load(json_file)
    return reservoir_properties


def get_time_coef(dict_property, objects, Wc, oilfield):
    """
    Рассчет коэффициента для формулы по вычислению времени исследования скважины
    При умножении этого коэффицента на радиус охвата, получаем время исследования
    :param oilfield: название месторождения
    :param Wc: обводненность
    :param objects: название пласта
    :param dict_property: словарь со свойствами всех пластов
    :return: возвращает коэффициент для расчета времени исследования
    """
    water_cut = Wc / 100
    list_obj = list(str(objects).split(','))
    num_obj = 0
    num_default = 0
    mu, ct, phi, k = 0, 0, 0, 0
    for obj in list_obj:
        obj = f'{oilfield}_{obj}'
        if obj in dict_property.keys():
            num_obj += 1
            K_rok = dict_property[obj]['K_rok']
            Kro_func = dict_property[obj]['Kro_func']
            Kro_degree = dict_property[obj]['Kro_degree']
            Krw_func = dict_property[obj]['Krw_func']
            Krw_degree = dict_property[obj]['Krw_degree']
            Sno = dict_property[obj]['Sno']
            Swo = dict_property[obj]['Swo']
            Swk = dict_property[obj]['Swk']
            mu_oil = dict_property[obj]['oil_visc']
            mu_water = dict_property[obj]['water_visc']
            oil_compr = dict_property[obj]['oil_compr'] / (1.03323 * 10 ** 5)
            water_compr = dict_property[obj]['water_copmr'] / (1.03323 * 10 ** 5)
            rock_compr = dict_property[obj]['rock_compr'] / (1.03323 * 10 ** 5)
            Sw = Swo + water_cut * (Swk - Swo)
            mu += (mu_oil * mu_water /
                   (water_cut * mu_oil + (1 - water_cut) * mu_water))
            ct += (1 - water_cut) * oil_compr + water_cut * water_compr + rock_compr
            phi += dict_property[obj]['phi'] / 100
            Kro = K_rok * (1 - (Sw - Swo) / (1 - Swo)) ** Kro_func * (1 - (Sw - Swo) / (1 - Swo)) ** (
                (2 + Kro_degree / Kro_degree))
            Krw = ((1 - Swo - Sno) / (1 - Swo)) ** Krw_func * ((Sw - Swo) / (1 - Swo)) ** Krw_degree
            k += mu * (Kro / mu_oil + Krw / mu_water)

        else:
            num_default += 1
            num_obj += 1
            K_rok = dict_property['DEFAULT_OBJ']['K_rok']
            Kro_func = dict_property['DEFAULT_OBJ']['Kro_func']
            Kro_degree = dict_property['DEFAULT_OBJ']['Kro_degree']
            Krw_func = dict_property['DEFAULT_OBJ']['Krw_func']
            Krw_degree = dict_property['DEFAULT_OBJ']['Krw_degree']
            Sno = dict_property['DEFAULT_OBJ']['Sno']
            Swo = dict_property['DEFAULT_OBJ']['Swo']
            Swk = dict_property['DEFAULT_OBJ']['Swk']
            mu_oil = dict_property['DEFAULT_OBJ']['oil_visc']
            mu_water = dict_property['DEFAULT_OBJ']['water_visc']
            oil_compr = dict_property['DEFAULT_OBJ']['oil_compr'] / (1.03323 * 10 ** 5)
            water_compr = dict_property['DEFAULT_OBJ']['water_copmr'] / (1.03323 * 10 ** 5)
            rock_compr = dict_property['DEFAULT_OBJ']['rock_compr'] / (1.03323 * 10 ** 5)
            Sw = Swo + water_cut * (Swk - Swo)
            mu += (mu_oil * mu_water /
                   (water_cut * mu_oil + (1 - water_cut) * mu_water))
            ct += (1 - water_cut) * oil_compr + water_cut * water_compr + rock_compr
            phi += dict_property['DEFAULT_OBJ']['phi'] / 100
            Kro = K_rok * (1 - (Sw - Swo) / (1 - Swo)) ** Kro_func * (1 - (Sw - Swo) / (1 - Swo)) ** (
                (2 + Kro_degree / Kro_degree))
            Krw = ((1 - Swo - Sno) / (1 - Swo)) ** Krw_func * ((Sw - Swo) / (1 - Swo)) ** Krw_degree
            k += (mu_oil * mu_water /
                  (water_cut * mu_oil + (1 - water_cut) * mu_water)) * (Kro / mu_oil + Krw / mu_water)

    time_coef = 462.2824 * (mu * ct * phi / k) / (len(list_obj) ** 2)

    return [time_coef, mu, ct, phi, k, num_default, num_obj]


def upload_parameters(path):
    """
    :param path: путь к файлу с параметрами расчета
    :return: возваращает словарь с параметрами расчета
    """
    with open(path, encoding='UTF-8') as f:
        dict_parameters = yaml.safe_load(f)

    gdis_file = dict_parameters['gdis_file']
    gdis_file = None if gdis_file == "нет" else gdis_file
    dict_parameters['gdis_file'] = gdis_file

    year = dict_parameters['gdis_option']  # how many years ago gdis was made
    year = None if year == "нет" else year
    dict_parameters['gdis_option'] = year

    separation = dict_parameters['separation_by_years']
    separation = None if separation == "нет" else separation
    dict_parameters['separation_by_years'] = separation

    exception = dict_parameters['exception_file']
    exception = None if exception == "нет" else exception
    dict_parameters['exception_file'] = exception

    return dict_parameters


def get_path():
    """
    :return: Функция возвращает путь, по которому находится exe файл
    """
    if getattr(sys, 'frozen', False):
        application_path = os.path.dirname(sys.executable)
    elif __file__:
        application_path = os.path.dirname(__file__)

    return application_path


def clean_work_horizon(df, count_of_hor):
    if (count_of_hor != 0) and (count_of_hor > 0):
        df['horizon_count'] = df['workHorizon'].apply(lambda x: len(set(x.replace(" ", "").split(","))))
        df = df[df['horizon_count'] <= count_of_hor]
        df.drop(columns=['horizon_count'], axis=1, inplace=True)
        return df
    elif count_of_hor == 0:
        return df
    else:
        raise TypeError(f'Wrong parameter {count_of_hor}. Expected values: 0, 1, 2...')


def exception_marker(list_exception, wellName, wellStatus, workMarker, PIEZ_STATUS, INJ_MARKER, INJ_STATUS):
    if (wellStatus == PIEZ_STATUS) and (wellName in list_exception):
        return ''
    elif (wellStatus in INJ_STATUS) and (workMarker == INJ_MARKER) and (wellName in list_exception):
        return ''
    else:
        return wellName
