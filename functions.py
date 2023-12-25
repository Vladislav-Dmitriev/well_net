import json
import os
import sys

import numpy as np
import yaml
from scipy.optimize import fsolve


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


def wc_func(x, water_cut, const, S_o_init, S_w_init, Corey_w, Corey_o):
    return -water_cut + (1 / (1 + const * (1 - x - S_o_init) ** Corey_o / (x - S_w_init) ** Corey_w))


def wc_func_derivative(x, const, S_o_init, S_w_init, Corey_w, Corey_o):
    return (Corey_o * const * (1 - x - S_o_init) ** (Corey_o - Corey_w) * (x - S_w_init) ** (- Corey_w)
            - Corey_w * const * (1 - x - S_o_init) ** Corey_o * (x - S_w_init) ** (- Corey_w - 1) /
            (1 + const * (1 - x - S_o_init) ** Corey_o / (x - S_w_init) ** Corey_w) ** 2)


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
        oilfield_obj = f'{oilfield}_{obj}'
        if oilfield_obj in dict_property.keys():
            # расчет свойств объектов, которые есть в PVT таблице
            num_obj += 1
            K_omax = dict_property[oilfield_obj]['K_omax']
            K_wmax = dict_property[oilfield_obj]['K_wmax']
            K_abs = dict_property[oilfield_obj]['K_abs']
            Kro_func = dict_property[oilfield_obj]['Kro_func']
            Kro_degree = dict_property[oilfield_obj]['Kro_degree']
            Krw_func = dict_property[oilfield_obj]['Krw_func']
            Krw_degree = dict_property[oilfield_obj]['Krw_degree']
            Sno = dict_property[oilfield_obj]['Sno']
            Swo = dict_property[oilfield_obj]['Swo']
            Swk = dict_property[oilfield_obj]['Swk']
            mu_oil = dict_property[oilfield_obj]['oil_visc']
            mu_water = dict_property[oilfield_obj]['water_visc']
            oil_compr = dict_property[oilfield_obj]['oil_compr'] / (1.03323 * 10 ** 5)
            water_compr = dict_property[oilfield_obj]['water_copmr'] / (1.03323 * 10 ** 5)
            rock_compr = dict_property[oilfield_obj]['rock_compr'] / (1.03323 * 10 ** 5)
            coef = mu_water * K_omax / (mu_oil * K_wmax * np.power(1 - Swo - Sno, Kro_func - Krw_func))

            if water_cut == 1:
                Sw = Swk
            elif water_cut == 0:
                Sw = Swo
            else:
                Sw = fsolve(lambda x: wc_func(x, water_cut, coef, Sno, Swo, Krw_func, Kro_func), 0.6)[0]

            mu += (mu_oil * mu_water /
                   (water_cut * mu_oil + (1 - water_cut) * mu_water))
            ct += (1 - Sw) * oil_compr + Sw * water_compr + rock_compr
            phi += dict_property[oilfield_obj]['phi'] / 100
            K_o = K_abs * K_omax * (np.power(1 - Sw - Sno, Kro_degree) / np.power(1 - Swo - Sno, Kro_degree))
            K_w = K_abs * K_wmax * (np.power(Sw - Swo, Krw_degree) / np.power(1 - Swo - Sno, Krw_degree))
            k += (mu_oil * mu_water /
                  (water_cut * mu_oil + (1 - water_cut) * mu_water)) * (K_o / mu_oil + K_w / mu_water)

        else:
            # расчет свойств объекта по умолчанию
            num_default += 1
            num_obj += 1
            K_wmax = dict_property['DEFAULT_OBJ']['K_wmax']
            K_omax = dict_property['DEFAULT_OBJ']['K_omax']
            K_abs = dict_property['DEFAULT_OBJ']['K_abs']
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
            coef = mu_water * K_omax / (mu_water * K_wmax * (1 - Swo - Sno))

            if water_cut == 1:
                Sw = Swk
            elif water_cut == 0:
                Sw = Swo
            else:
                Sw = fsolve(lambda x: wc_func(x, water_cut, coef, Sno, Swo, Krw_func, Kro_func), 0.6)[0]

            mu += (mu_oil * mu_water /
                   (water_cut * mu_oil + (1 - water_cut) * mu_water))
            ct += (1 - Sw) * oil_compr + Sw * water_compr + rock_compr
            phi += dict_property['DEFAULT_OBJ']['phi'] / 100
            K_o = K_abs * K_omax * (np.power(1 - Sw - Sno, Kro_func) / np.power(1 - Swo - Sno, Kro_func))
            K_w = K_abs * K_wmax * (np.power(Sw - Swo, Krw_func) / np.power(1 - Swo - Sno, Krw_func))
            k += (mu_oil * mu_water /
                  (water_cut * mu_oil + (1 - water_cut) * mu_water)) * (K_o / mu_oil + K_w / mu_water)

    # time_coef = 462.2824 * (mu * ct * phi / k) / (len(list_obj) ** 2)
    mu = mu / num_obj
    ct = ct / num_obj
    phi = phi / num_obj
    k = k / num_obj
    time_coef = 462.2824 * (mu * ct * phi / k)

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
    if (wellStatus in PIEZ_STATUS) and (str(wellName) in list_exception):
        return ''
    elif (wellStatus in INJ_STATUS) and (workMarker in INJ_MARKER) and (str(wellName) in list_exception):
        return ''
    else:
        return wellName
