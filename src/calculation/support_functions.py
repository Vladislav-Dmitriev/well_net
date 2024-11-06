import json
import math
import os
import sys
import numpy as np
import pandas as pd
import yaml
from loguru import logger
from scipy.optimize import fsolve
from tqdm import tqdm


@logger.catch(level='DEBUG')
def unpack_status(dict_constant):
    """
    Распаковка параметров из словаря, для удобства использования в коде
    :param dict_constant: словарь со статусами скважин и характером их работы
    :return: возвращает статусы и характер работы скважин как отдельные переменные типа string
    """
    return dict_constant.get("PROD_STATUS"), dict_constant.get("PROD_MARKER"), dict_constant.get("PIEZ_STATUS"), \
        dict_constant.get("INJ_MARKER"), dict_constant.get("INJ_STATUS"), dict_constant.get("DELETE_STATUS")


@logger.catch(level='DEBUG')
def get_property(path):
    """
    Считывание параметров из yaml-файла в словарь
    :param path: путь к файлу с параметрами
    :return: возвращает словарь с параметрами по ключу объекта
    """
    with open(path, encoding='UTF-8') as json_file:
        reservoir_properties = json.load(json_file)
    return reservoir_properties


@logger.catch(level='DEBUG')
def wc_func(x, water_cut, const, S_o_init, S_w_init, Corey_w, Corey_o):
    """
    Функция зависимости обводненности от водонасыщенности
    :param x: начальное приближение для поиска корня уравнения
    :param water_cut: обводненность
    :param const: коэффициент перед функцией (начальная водонасыщенность, остаточная нефтенасыщенность, вязкости, проницаемости)
    :param S_o_init: остаточная нефтенасыщенность
    :param S_w_init: начальная водонасыщенность
    :param Corey_w: степень Кори для воды
    :param Corey_o: степень Кори для нефти
    :return: возвращает значение функции обводненности
    """
    return -water_cut + (1 / (1 + const * (1 - x - S_o_init) ** Corey_o / (x - S_w_init) ** Corey_w))


@logger.catch(level='DEBUG')
def get_time_coef(dict_property, objects, Wc, oilfield, gas_status):
    """
    Рассчет коэффициента для формулы по вычислению времени исследования скважины
    При умножении этого коэффицента на радиус охвата, получаем время исследования
    :param gas_status: тип скважины для выбора формулы расчета времени КВД (нефтяная, газовая, газоконденсатная,
     водонагнетательная, газонагнетательная, поглощающая, пьезометрическая)
    :param oilfield: название месторождения
    :param Wc: обводненность
    :param objects: название пласта
    :param dict_property: словарь со свойствами всех пластов
    :return: возвращает коэффициент для расчета времени исследования
    """
    water_cut = Wc / 100
    list_obj = list(str(objects).split(', '))
    mu, ct, phi, k, gas_viscocity, pressure, num_default, num_obj = 0, 0, 0, 0, 0, 0, 0, 0

    for obj in tqdm(list_obj, "Calculate time coefficient for objects of well", position=0, leave=True, colour='white',
                    ncols=80, disable=True):
        if obj in dict_property[oilfield].keys():
            num_obj += 1
            # расчет свойств объектов, которые есть в PVT таблице
            K_omax = dict_property[oilfield][obj]['K_omax']
            K_wmax = dict_property[oilfield][obj]['K_wmax']
            K_abs = dict_property[oilfield][obj]['K_abs']
            Kro_func = dict_property[oilfield][obj]['Kro_func']
            Kro_degree = dict_property[oilfield][obj]['Kro_degree']
            Krw_func = dict_property[oilfield][obj]['Krw_func']
            Krw_degree = dict_property[oilfield][obj]['Krw_degree']
            Sno = dict_property[oilfield][obj]['Sno']
            Swo = dict_property[oilfield][obj]['Swo']
            Swk = dict_property[oilfield][obj]['Swk']
            mu_oil = dict_property[oilfield][obj]['oil_visc']
            mu_water = dict_property[oilfield][obj]['water_visc']
            oil_compr = dict_property[oilfield][obj]['oil_compr'] / (1.03323 * 10 ** 5)
            water_compr = dict_property[oilfield][obj]['water_copmr'] / (1.03323 * 10 ** 5)
            rock_compr = dict_property[oilfield][obj]['rock_compr'] / (1.03323 * 10 ** 5)
            gas_viscocity += dict_property[oilfield][obj]['gas_visc']
            pressure += dict_property[oilfield][obj]['pressure']
            coef = mu_water * K_omax / (mu_oil * K_wmax * np.power(1 - Swo - Sno, Kro_func - Krw_func))

            if water_cut == 1:
                Sw = Swk
            elif water_cut == 0:
                Sw = Swo
            else:
                Sw = fsolve(lambda x: wc_func(x, water_cut, coef, Sno, Swo, Krw_func, Kro_func), np.array(0.5))[0]

            mu += ((mu_oil + mu_water) /
                   (water_cut * mu_oil + (1 - water_cut) * mu_water))
            ct += (1 - Sw) * oil_compr + Sw * water_compr + rock_compr
            phi += dict_property[oilfield][obj]['porosity'] / 100
            K_o = K_abs * K_omax * (np.power(1 - Sw - Sno, Kro_func) / np.power(1 - Swo - Sno, Kro_func))
            if math.isnan(K_o):
                K_o = 0
            K_w = K_abs * K_wmax * (np.power(Sw - Swo, Krw_degree) / np.power(1 - Swo - Sno, Krw_func))
            if math.isnan(K_w):
                K_w = 0
            k += ((mu_oil + mu_water) /
                  (water_cut * mu_oil + (1 - water_cut) * mu_water)) * (K_o / mu_oil + K_w / mu_water)

        else:
            # расчет свойств объекта по умолчанию
            num_default += 1
            K_wmax = dict_property[oilfield]['DEFAULT_OBJ']['K_wmax']
            K_omax = dict_property[oilfield]['DEFAULT_OBJ']['K_omax']
            K_abs = dict_property[oilfield]['DEFAULT_OBJ']['K_abs']
            Kro_func = dict_property[oilfield]['DEFAULT_OBJ']['Kro_func']
            Kro_degree = dict_property[oilfield]['DEFAULT_OBJ']['Kro_degree']
            Krw_func = dict_property[oilfield]['DEFAULT_OBJ']['Krw_func']
            Krw_degree = dict_property[oilfield]['DEFAULT_OBJ']['Krw_degree']
            Sno = dict_property[oilfield]['DEFAULT_OBJ']['Sno']
            Swo = dict_property[oilfield]['DEFAULT_OBJ']['Swo']
            Swk = dict_property[oilfield]['DEFAULT_OBJ']['Swk']
            mu_oil = dict_property[oilfield]['DEFAULT_OBJ']['oil_visc']
            mu_water = dict_property[oilfield]['DEFAULT_OBJ']['water_visc']
            oil_compr = dict_property[oilfield]['DEFAULT_OBJ']['oil_compr'] / (1.03323 * 10 ** 5)
            water_compr = dict_property[oilfield]['DEFAULT_OBJ']['water_copmr'] / (1.03323 * 10 ** 5)
            rock_compr = dict_property[oilfield]['DEFAULT_OBJ']['rock_compr'] / (1.03323 * 10 ** 5)
            gas_viscocity += dict_property[oilfield]['DEFAULT_OBJ']['gas_visc']
            pressure += dict_property[oilfield]['DEFAULT_OBJ']['pressure']
            coef = mu_water * K_omax / (mu_water * K_wmax * (1 - Swo - Sno))

            if water_cut == 1:
                Sw = Swk
            elif water_cut == 0:
                Sw = Swo
            else:
                Sw = fsolve(lambda x: wc_func(x, water_cut, coef, Sno, Swo, Krw_func, Kro_func), np.array(0.5))[0]

            mu += ((mu_oil + mu_water) /
                   (water_cut * mu_oil + (1 - water_cut) * mu_water))
            ct += (1 - Sw) * oil_compr + Sw * water_compr + rock_compr
            phi += dict_property[oilfield]['DEFAULT_OBJ']['porosity'] / 100
            K_o = K_abs * K_omax * (np.power(1 - Sw - Sno, Kro_func) / np.power(1 - Swo - Sno, Kro_func))
            if math.isnan(K_o):
                K_o = 0
            K_w = K_abs * K_wmax * (np.power(Sw - Swo, Krw_func) / np.power(1 - Swo - Sno, Krw_func))
            if math.isnan(K_w):
                K_w = 0
            k += ((mu_oil + mu_water) /
                  (water_cut * mu_oil + (1 - water_cut) * mu_water)) * (K_o / mu_oil + K_w / mu_water)

    mu = mu / (num_obj + num_default)
    ct = ct / (num_obj + num_default)
    phi = phi / (num_obj + num_default)
    k = k / (num_obj + num_default)
    gas_viscocity = gas_viscocity / (num_obj + num_default)
    pressure = (pressure / (num_obj + num_default)) / 1.033
    if 'газ' in str(gas_status).lower() and gas_viscocity == 0:
        time_coef = phi * 0.01938265 / (4 * k * pressure * 3600 * 24 * 10 ** (-7))
    elif 'газ' in str(gas_status).lower() and gas_viscocity != 0:
        time_coef = phi * gas_viscocity / (4 * k * pressure * 3600 * 24 * 10 ** (-7))
    else:
        time_coef = 462.2824 * (mu * ct * phi / k) / 24  # сутки

    return [time_coef, mu, ct, phi, k, gas_viscocity, pressure, num_default, len(list_obj)]


@logger.catch(level='DEBUG')
def dict_keys(list_r, contour_name):
    """
    :param list_r: список коэффициентов для умножения радиуса
    :param contour_name: имя контура
    :return: словарь с ключами из коэффициентов и имени текущего контура
    """
    list_keys = [f'{contour_name} k={x}' for x in list_r]
    dict_result = dict.fromkeys(list_keys, [pd.DataFrame(), None])
    return dict_result


@logger.catch(level='DEBUG')
def upload_parameters(path):
    """
    Функция загрузки заданных пользователем параметров
    :param path: путь к файлу с параметрами расчета
    :return: возваращает словарь с параметрами расчета
    """
    with open(path, encoding='UTF-8') as f:
        dict_parameters = yaml.safe_load(f)

    # коэффициенты кратного увеличения радиуса исследования
    mult_coef = str(dict_parameters['mult_coef'])
    mult_coef = mult_coef.split(',')
    try:
        mult_coef = [float(x) for x in mult_coef]
        dict_parameters['mult_coef'] = mult_coef
    except ValueError:
        dict_parameters['mult_coef'] = 1
        logger.info('Wrong type of radius mult coefficients. Default mult coefficient is 1')

    # дата последнего проведенного ГДИС
    year = dict_parameters['gdis_option']  # how many years ago gdis was made
    year = None if year == "нет" else year
    dict_parameters['gdis_option'] = str(year)

    #  кол-во лет для распределения по годам скважин в слепых зонах для ГДИС
    separation = dict_parameters['separation_by_years']
    separation = None if separation == "нет" else separation
    dict_parameters['separation_by_years'] = separation

    # параметр для 2 сценария (порядок построения регулярной сети из разных фондов [доб, наг, пьез])
    list_order = dict_parameters['list_order_fond']
    list_order = (list_order.upper()).split(', ')
    dict_parameters['list_order_fond'] = list_order

    # отбрасывать из добывающего фонда скважины с дебитом выше среднего по объекту
    mean_oilrate = dict_parameters['mean_oilrate_option']
    mean_oilrate = False if (str(mean_oilrate).lower() == "нет" or mean_oilrate is None) else mean_oilrate
    mean_oilrate = True if str(mean_oilrate).lower() == "да" else mean_oilrate
    dict_parameters['mean_oilrate_option'] = mean_oilrate

    limit_research = dict_parameters['limit_research_time']
    limit_research = False if ((str(limit_research).lower() == 'нет') or (limit_research is None)) else limit_research
    limit_research = True if limit_research == 'да' else limit_research
    dict_parameters['limit_research_time'] = limit_research

    option_percent = dict_parameters['option_percent']
    option_percent = False if (option_percent is None or str(option_percent).lower() == 'нет') else option_percent
    option_percent = True if str(option_percent).lower() == 'да' else option_percent
    dict_parameters['option_percent'] = option_percent

    return dict_parameters


@logger.catch(level='DEBUG')
def get_path():
    """
    :return: Функция возвращает путь, по которому находится exe файл
    """
    if getattr(sys, 'frozen', False):
        application_path = os.path.dirname(sys.executable)
        return application_path
    elif __file__:
        application_path = '\\'.join((os.path.dirname(__file__).split('\\')[:-2]))
        return application_path
    else:
        raise Exception('Executable file path not found')
    # if getattr(sys, 'frozen', False):
    #     # Возвращаем директорию, в которой находится .exe файл
    #     return os.path.dirname(sys.executable)
    # else:
    #     # Если программа запущена как скрипт, возвращаем директорию, где находится main.py
    #     return os.path.dirname(os.path.dirname(os.path.abspath(sys.argv[0])))



@logger.catch(level='DEBUG')
def clean_work_horizon(df, count_of_hor):
    """
    Удаляет из DataFrame скважины с числом объектов работы больше заданного пользователем

    :param df: база данных
    :param count_of_hor: максимальное кол-во объектов работы скважины, задается пользователем
    :return: DataFrame со скважинами, число объектов работы которых не превышает заданного пользователем кол-ва
    """
    df_exception = pd.DataFrame()
    if (not count_of_hor is None) and (count_of_hor > 0) and (count_of_hor != ''):
        df['horizon_count'] = df['workHorizon'].apply(lambda x: len(set(x.replace(" ", "").split(","))))
        df_exception = pd.concat([df_exception, df[df['horizon_count'] > count_of_hor]],
                                 axis=0, sort=False).reset_index(drop=True)
        df = df[df['horizon_count'] <= count_of_hor]
        df.drop(columns=['horizon_count'], axis=1, inplace=True)
        return df, df_exception
    else:
        logger.info('Value of well`s horizon count was left as a default')
        return df, df_exception


@logger.catch(level='DEBUG')
def delete_logfiles(mypath):
    """
    Удаление логфайлов предыдущих расчетов по указанному пути
    :param mypath: абсолютный путь к папке с логфайлами
    :return:
    """
    list_logfiles = [f for f in os.listdir(path=mypath) if f.endswith('.log')]
    for logfile in list_logfiles:
        os.remove(f'{mypath}{logfile}')
    pass


@logger.catch(level='DEBUG')
def rgb_to_ycc(r, g, b):
    """
    Перевод цвета из RGB в YCbCr
    :param r: число, характеризующее расстояние по вектору красного цвета в RGB
    :param g: число, характеризующее расстояние по вектору зеленого цвета в RGB
    :param b: число, характеризующее расстояние по вектору синего цвета в RGB
    :return: числа, переведенные из пространства RGB в пространство YCbCr
    """
    y = .299*r + .587*g + .114*b
    cb = 128 - .168736*r - .331364*g + .5*b
    cr = 128 + .5*r - .418688*g - .081312*b
    return y, cb, cr


@logger.catch(level='DEBUG')
def to_ycc(color):
    """
    Нормирование каждого числа RGB вектора
    :param color: кортеж из оттенков цвета RGB
    :return: нормированный по оттенкам цвет RGB и переведенный в пространство YCbCr
    """
    """ converts color tuples to floats and then to yuv """
    return rgb_to_ycc(*[x/255.0 for x in color])


@logger.catch(level='DEBUG')
def color_dist(c1, c2):
    """
    Возвращает расстояние цвета пользователя в RGB до одного из основных цветов пространства

    :param c1: цвет в RGB
    :param c2: один из основных цветов в RGB (итерация по основным цветам)
    :return: квадрат евклидова расстояния между двумя векторами цветов в пространстве YUV
    """
    return sum((a-b)**2 for a, b in zip(to_ycc(c1), to_ycc(c2)))


@logger.catch(level='DEBUG')
def min_color_diff(color_to_match, colors):
    """
    Возвращает минимальное расстояние до одного из цветов в пространстве YCbCr и имя цвета
    :param color_to_match: цвет, оттенок которого нудно определить
    :param colors: цвет из списка основных цветов RGB
    :return: минимальное расстояние до одного из основных цветов RGB и название цвета
    """
    return min((color_dist(color_to_match, test), colors[test]) for test in colors)