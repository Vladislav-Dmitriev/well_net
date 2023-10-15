import os

import geopandas as gpd
import pandas as pd
import xlwings as xw
import yaml
from shapely.geometry import LineString, Point, Polygon
from tqdm import tqdm


def get_polygon_well(R_well, type_well, *coordinates):
    """
    Создание зоны вокруг скважины с заданным радиусом
    :param R_well: радиус создания зоны
    :param type_well: тип скважины
    :param coordinates: координаты устье/забой
    :return: возвращает геометрический объект зоны вокруг скважины
    """
    if type_well == "vertical":
        well_polygon = Point(coordinates[0], coordinates[1]).buffer(R_well)
        return well_polygon
    elif type_well == "horizontal":
        t1 = Point(coordinates[0], coordinates[1])
        t3 = Point(coordinates[2], coordinates[3])
        well_polygon = LineString([t1, t3]).buffer(R_well, join_style=1)
        return well_polygon
    else:
        raise NameError(f"Wrong well type: {type_well}. Allowed values: vertical or horizontal")


def check_intersection_area(area, df_points, percent, calc_option=True):
    """
    Проверка входят ли скважины из df_point в зону другой скважины area
    :param percent: процент попадания скважины в зону охвата area
    :param calc_option: флаг переключения сценария охвата скважин
    :param area: координаты зоны вокруг конкретной скважины
    :param df_points: данные из которых берется геометрия скважин(точки/линии)
    :return: возвращаются имена скважин, которые входят в данную зону area
    """
    if calc_option:
        '''Столбец GEOMETRY позволит включать скважины в зону охвата,
        если скважина попадает в нее на определенное кол-во процентов'''
        df_points = gpd.GeoDataFrame(df_points, geometry="GEOMETRY")
        df_points = df_points[(df_points["GEOMETRY"].intersects(area))]
        df_points['part_in'] = list(map(lambda x: area.intersection(x).length / x.length if x.length != 0 else 1,
                                        df_points["GEOMETRY"]))
        df_points = df_points[df_points['part_in'] >= percent / 100]
        df_points.drop(columns=['part_in'], axis=1, inplace=True)
        return df_points.wellName.values
    elif not calc_option:
        '''столбец POINT будет включать в зону охвата только те скважины,
        у которых точка входа в пласт попадает в зону охвата'''
        df_points = gpd.GeoDataFrame(df_points, geometry="POINT")
        df_points = df_points[df_points["POINT"].intersects(area)]
        return df_points.wellName.values
    else:
        raise TypeError(f'Wrong calculation option type: {calc_option}. Expected values: True or False')


def unpack_status(dict_constant):
    """
    Распаковка параметров из словаря, для удобства использования в коде
    :param dict_constant: словарь со статусами скважин и характером их работы
    :return: возвращает статусы и характер работы скважин как отдельные переменные типа string
    """
    return dict_constant.get("PROD_STATUS"), dict_constant.get("PROD_MARKER"), dict_constant.get("PIEZ_STATUS"), \
        dict_constant.get("INJ_MARKER"), dict_constant.get("INJ_STATUS")


def check_intersection_point(point, df_areas, percent, calc_option=True):
    """
    Функция позволяет узнать, перечесение со сколькими зонами имеет определенная скважина
    :param calc_option: флаг переключения сценария охвата скважин
    :param percent: процент попадания скважины в зону охвата
    :param point: геометрия скважины(точка/линия)
    :param df_areas: DataFrame со столбцом зон вокруг скважин
    :return: перечесение со сколькими зонами имеет определенная скважина
    """
    if calc_option:
        df_areas = gpd.GeoDataFrame(df_areas, geometry="AREA")
        df_areas = df_areas[df_areas["AREA"].intersects(point)]
        df_areas['part_in'] = list(
            map(lambda x: point.intersection(x).length / point.length if point.length != 0 else 1,
                df_areas.AREA))
        df_areas = df_areas[df_areas['part_in'] >= percent / 100]
        df_areas.drop(columns=['part_in'])
        return df_areas.wellName.values
    elif not calc_option:
        df_areas = gpd.GeoDataFrame(df_areas, geometry="AREA")
        df_areas = df_areas[df_areas["AREA"].intersects(point)]
        return df_areas.wellName.values
    else:
        raise TypeError(f'Wrong calculation option type: {calc_option}. Expected values: True or False')


def intersect_number(df_prod, df_inj_piez, percent):
    """
    Функция добавляет в DataFrame столбец 'intersection', в него записываются
    имена скважин из другого DataFrame, с которыми пересекается текущая, затем добавляется
    столбец 'number', в который заносится кол-во пересечений конкретной скважины с остальными
    :param percent: процент попадания скважины в зону охвата
    :param df_prod: добывающие
    :param df_inj_piez: нагнетательные/пьезометры
    :return: возвращаются DataFrame с кол-вом пересечений
    """
    if ("intersection" not in df_inj_piez) & ("number" not in df_inj_piez):
        df_inj_piez.insert(loc=df_inj_piez.shape[1], column="intersection", value=0)
        df_inj_piez.insert(loc=df_inj_piez.shape[1], column="number", value=0)

    if ("intersection" not in df_prod) & ("number" not in df_prod):
        df_prod.insert(loc=df_prod.shape[1], column="intersection", value=0)
        df_prod.insert(loc=df_prod.shape[1], column="number", value=0)

    df_inj_piez["intersection"] = list(map(lambda x: check_intersection_area(x, df_prod, percent, True),
                                           df_inj_piez.AREA))
    df_inj_piez["number"] = list(map(lambda x: len(x), df_inj_piez.intersection))
    df_inj_piez = df_inj_piez[df_inj_piez.number > 0]
    df_prod["intersection"] = list(map(lambda x: check_intersection_point(x, df_inj_piez, percent, True),
                                       df_prod.POINT))
    df_prod["number"] = list(map(lambda x: len(x), df_prod.intersection))
    return df_prod, df_inj_piez


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
    # выделяем пьезометры/нагнетательные из добывающих, у которых только 1 пересечение
    list_inj_piez_wells += list(df_prod[df_prod.number == 1].intersection.explode().unique())
    list_prod_wells = df_inj_piez[
        df_inj_piez.wellName.isin(list_inj_piez_wells)].intersection.explode().unique()
    # создаем dataframe оптимизации, исключая скважины с одним пересечением
    df_optim = df_inj_piez[~df_inj_piez.wellName.isin(list_inj_piez_wells)]
    df_optim.intersection = list(
        map(lambda x: list(set(x).difference(set(list_prod_wells))), df_optim.intersection))
    df_optim.number = list(map(lambda x: len(x), df_optim.intersection))
    # отсеиваются одиночные скважины, не имеющие пересечений
    df_optim = df_optim[df_optim.number > 0]
    # в df_optim остались скважины с ненулевыми пересечениями
    if not df_optim.empty:
        #  создаем сет уникальных значений столбца с пересечениями и сортируем dataframe по кол-ву пересечений
        set_visible_wells = set(df_optim.intersection.explode().unique())
        df_optim = df_optim.sort_values(by=['number'], ascending=True)
        # на каждой итерации создается набор исключений, кроме итерируемой скважины,
        # он сравнивается с набором скважин, входящих в список перечесений выше
        for well in df_optim.wellName.values:
            set_exception = set(df_optim[df_optim.wellName != well].intersection.explode().unique())
            # при совпадении наборов исключений и пересечений из df_optim исключается итерируемая скважина
            # и добавляется к списку нагн./пьез.
            if set_exception == set_visible_wells:
                df_optim = df_optim[df_optim.wellName != well]
        list_inj_piez_wells += list(df_optim.wellName.values)

    return list_inj_piez_wells


def add_shapely_types(df_input, mean_radius, coeff):
    """
    Добавление в DataFrame столбца с площадью охвата скважин, в зависимости от среднего радиуса охвата по контуру
    :param coeff: коэффициент домножения радиуса
    :param df_input: DataFrame, полученный из исходного файла
    :param mean_radius: средний радиус окружения для итерируемого объекта
    :return: Возвращается DataFrame с добавленными столбцами геометрии и площади влияния каждой скважины
    """
    if 'AREA' not in df_input:
        df_input.insert(loc=df_input.shape[1], column="AREA", value=0)

    df_input["AREA"] = df_input["AREA"].where(
        df_input["well type"] != "vertical", list(map(lambda x, y: get_polygon_well(
            mean_radius * coeff, "vertical", x, y), df_input.coordinateX, df_input.coordinateY)))
    df_input["AREA"] = df_input["AREA"].where(df_input["well type"] != "horizontal",
                                              list(map(lambda x, y, x1, y1:
                                                       get_polygon_well(
                                                           mean_radius * coeff, "horizontal", x, y, x1, y1),
                                                       df_input.coordinateX,
                                                       df_input.coordinateY,
                                                       df_input.coordinateX3,
                                                       df_input.coordinateY3)))

    return df_input


def write_to_excel(dict_result, **dict_constant):
    """
    Для записи результата расчетов в Excel подается словарь
    Для каждого ключа создается отдельный лист в документе
    :param dict_constant: словарь со статусами скважин
    :param dict_result: словарь, по ключам которого содержатся DataFrame для каждого контура
    :return: функция сохраняет файл в указанную директорию
    """
    app1 = xw.App(visible=False)
    new_wb = xw.Book()

    for key, value in tqdm(dict_result.items(), "Write to excel file", position=0, leave=False, ncols=80):
        name = str(key).replace("/", " ")
        if f"{name}" in new_wb.sheets:
            xw.Sheet[f"{name}"].delete()
        new_wb.sheets.add(f"{name}")
        sht = new_wb.sheets(f"{name}")
        df = value[0]
        df["intersection"] = list(map(lambda x: " ".join(str(y) for y in x), df["intersection"]))
        del df["POINT"]
        del df["POINT3"]
        del df["GEOMETRY"]
        del df["AREA"]
        sht.range('A1').options().value = df
    df_report = get_report(dict_result, **dict_constant)
    if "report" in new_wb.sheets:
        xw.Sheet["report"].delete()
    new_wb.sheets.add("report")
    sht = new_wb.sheets("report")
    sht.range('A1').options().value = df_report
    new_wb.save("output\out_file_geometry.xlsx")
    # End print
    app1.kill()
    pass


def get_report(dict_result, **dict_constant):
    """
    Функция для создания краткого отчета по всем контурам с разными коэффициентами для радиусов охвата
    :param dict_result: словарь с результатами расчетов по всем объектам
    :param dict_constant: словарь со статусами скважин
    :return: возвращает DataFrame с отчетом по каждому контуру с определенным коэффициентом домножения радиуса
    """
    dict_names_report = {'Сценарий': "contour_k",
                         'Кол-во объектов': "obj_count",
                         'Средний радиус': "mean_rad",
                         'Среднее время исследования': "mean_time",
                         'Кол-во пьезометров': "piez_count",
                         'Кол-во нагн': "inj_count",
                         'Кол-во доб': "prod_count",
                         'Кол-во исслед. скв. текущ. год': "well_quantity0",
                         'Кол-во исслед. скв. 1 год': "well_quantity1",
                         'Кол-во исслед. скв. 2 год': "well_quantity2",
                         'Охваченные исследованиями текущ. год': "research_wells0",
                         'Охваченные исследованиями 1 год': "research_wells1",
                         'Охваченные исследованиями 2 год': "research_wells2",
                         'Потери нефти текущ. год, т': "oil_loss0",
                         'Потери нефти 1 год, т': "oil_loss1",
                         'Потери нефти 2 год, т': "oil_loss2",
                         'Потери закачки текущ. год, м3': "injection_loss0",
                         'Потери закачки 1 год, м3': "injection_loss1",
                         'Потери закачки 2 год, м3': "injection_loss2"}

    PROD_STATUS, PROD_MARKER, PIEZ_STATUS, INJ_MARKER, INJ_STATUS = unpack_status(dict_constant)
    dict_report = {}

    for key, value in dict_result.items():
        df = value[0]

        dict_report['contour_k'] = dict_report.get('contour_k', []) + [key]
        dict_report['obj_count'] = dict_report.get('obj_count', []) + [len(set(df['workHorizon'].explode().unique()))]
        dict_report['mean_rad'] = dict_report.get('mean_rad', []) + [df['mean_radius'].mean()]
        dict_report['mean_time'] = dict_report.get('mean_time', []) + [df['research_time'].mean()]
        dict_report['piez_count'] = dict_report.get('piez_count', []) + [len(df.loc[df.wellStatus == PIEZ_STATUS])]
        dict_report['inj_count'] = dict_report.get('inj_count', []) + [len(
            df.loc[(df.workMarker == INJ_MARKER) & (df.wellStatus.isin(INJ_STATUS))])]
        dict_report['prod_count'] = dict_report.get('prod_count', []) + [len(
            df.loc[(df.workMarker == PROD_MARKER) & (df.wellStatus.isin(PROD_STATUS))])]

        dict_report['well_quantity0'] = dict_report.get('well_quantity0', []) + [df[df['year_of_survey'] == 0].shape[0]]
        dict_report['well_quantity1'] = (dict_report.get('well_quantity1', []) +
                                         [df[df['year_of_survey'] == 1].shape[0]])
        dict_report['well_quantity2'] = (dict_report.get('well_quantity2', []) +
                                         [df[df['year_of_survey'] == 2].shape[0]])

        dict_report['research_wells0'] = (dict_report.get('research_wells0', []) +
                                          [len(set(df[df['year_of_survey'] == 0].intersection.explode().unique()))])
        dict_report['research_wells1'] = dict_report.get('research_wells1', []) + [
            len(set(df[df['year_of_survey'] == 1].intersection.explode().unique()))]
        dict_report['research_wells2'] = dict_report.get('research_wells2', []) + [
            len(set(df[df['year_of_survey'] == 2].intersection.explode().unique()))]

        dict_report['oil_loss0'] = dict_report.get('oil_loss0', []) + [df[df['year_of_survey'] == 0].oil_loss.sum()]
        dict_report['oil_loss1'] = dict_report.get('oil_loss1', []) + [df[df['year_of_survey'] == 1].oil_loss.sum()]
        dict_report['oil_loss2'] = dict_report.get('oil_loss2', []) + [df[df['year_of_survey'] == 2].oil_loss.sum()]

        dict_report['injection_loss0'] = (dict_report.get('injection_loss0', []) +
                                          [df[df['year_of_survey'] == 0].injection_loss.sum()])
        dict_report['injection_loss1'] = (dict_report.get('injection_loss1', []) +
                                          [df[df['year_of_survey'] == 1].injection_loss.sum()])
        dict_report['injection_loss2'] = dict_report.get('injection_loss2', []) + [
            df[df['year_of_survey'] == 2].injection_loss.sum()]

    df_report = pd.DataFrame.from_dict(dict_report, orient='columns')
    df_report.rename(columns=dict_names_report, inplace=True)

    return df_report


def load_contour(contour_path):
    """
    Загрузка файла с координатами контура и построение многоугольника
    :param contour_path: Путь к файлу с координатами контура
    :return: Возвращается многоугольник GeoPandas на основе координат из файла
    """
    columns_name = ['coordinateX', 'coordinateY']
    df_contour = pd.read_csv(contour_path, sep=' ', decimal=',', header=0, names=columns_name)
    gdf_contour = gpd.GeoDataFrame(df_contour)
    list_of_coord = [[x, y] for x, y in zip(gdf_contour.coordinateX, gdf_contour.coordinateY)]
    polygon = Polygon(list_of_coord)
    return polygon


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
    with open(path, 'rt', encoding='utf8') as yml:
        reservoir_properties = yaml.load(yml, Loader=yaml.Loader)
    return reservoir_properties


def get_time_coef(path, list_obj, *parameters):
    """
    Рассчет коэффициента для формулы по вычислению времени исследования скважины
    При умножении этого коэффицента на радиус охвата, получаем время исследования
    :param list_obj: список объектов
    :param path: путь к файлу с параметрами
    :param parameters: набор необходимых параметров для расчета времени исследования
    :return: возвращает коэффициент для расчета времени исследования
    """
    dict_property = get_property(path)
    mu, ct, phi, k = 0, 0, 0, 0
    for obj in list_obj:
        if obj in dict_property.keys():
            mu += dict_property[obj][parameters[0]]
            ct += dict_property[obj][parameters[1]]
            phi += dict_property[obj][parameters[2]]
            k += dict_property[obj][parameters[3]]

        else:
            mu += dict_property['DEFAULT_OBJ'][parameters[0]]
            ct += dict_property['DEFAULT_OBJ'][parameters[1]]
            phi += dict_property['DEFAULT_OBJ'][parameters[2]]
            k += dict_property['DEFAULT_OBJ'][parameters[3]]
    time_coef = 462.2824 * (mu * ct * phi / k) / (len(list_obj) ** 2)
    return time_coef


def clean_pictures_folder(path):
    """
    Функция очищает папку с рисунками предыдущего расчета
    :param path: путь к папке с рисунками
    :return: не возвращает объектов, удаляет содержимое папки
    """
    for f in os.listdir(path):
        os.remove(os.path.join(path, f))
    pass


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
    separation = None if gdis_file == "нет" else separation
    dict_parameters['separation_by_years'] = separation

    return dict_parameters
