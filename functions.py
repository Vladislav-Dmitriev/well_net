from shapely.geometry import LineString, Point
import geopandas as gpd
import xlwings as xw
import pandas as pd
from shapely.geometry import Polygon
import yaml
from loguru import logger
from statistics import mean


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


def check_intersection_area(area, df_points):
    """
    Проверка входят ли скважины из df_point в зону другой скважины area
    :param area: координаты зоны вокруг конкретной скважины
    :param df_points: данные из которых берется геометрия скважин(точки/линии)
    :return: возвращаются имена скважин, которые входят в данную зону area
    """
    df_points = gpd.GeoDataFrame(df_points, geometry="GEOMETRY")
    df_points = df_points[df_points["GEOMETRY"].intersects(area)]
    return df_points.wellName.values


def unpack(dict_constant):
    """
    Распаковка параметров из словаря, для удобства использования в коде
    :param dict_constant: словарь со статусами скважин и характером их работы
    :return: возвращает статусы и характер работы скважин как отдельные переменные типа string
    """
    return dict_constant.get("PROD_STATUS"), dict_constant.get("PROD_MARKER"), dict_constant.get("PIEZ_STATUS"), \
        dict_constant.get("INJ_MARKER"), dict_constant.get("INJ_STATUS")


def check_intersection_point(point, df_areas):
    """
    Функция позволяет узнать, перечесение со сколькими зонами имеет определенная скважина
    :param point: геометрия скважины(точка/линия)
    :param df_areas: DataFrame со столбцом зон вокруг скважин
    :return: перечесение со сколькими зонами имеет определенная скважина
    """
    df_areas = gpd.GeoDataFrame(df_areas, geometry="AREA")
    df_areas = df_areas[df_areas["AREA"].intersects(point)]
    return df_areas.wellName.values


def intersect_number(df_prod, df_inj_piez):
    """
    Функция добавляет в DataFrame столбец 'intersection', в него записываются
    имена скважин, с которыми пересекается текущая, затем добавляется
    столбец 'number', в который заносится кол-во пересечений конкретной скважины с остальными
    :param df_prod: добывающие
    :param df_inj_piez: нагнетательные/пьезометры
    :return: возвращаются DataFrame с кол-вом пересечений
    """
    df_inj_piez.insert(loc=df_inj_piez.shape[1], column="intersection",
                       value=list(map(lambda x: check_intersection_area(x, df_prod),
                                      df_inj_piez.AREA)))
    df_inj_piez.insert(loc=df_inj_piez.shape[1], column="number",
                       value=list(map(lambda x: len(x), df_inj_piez.intersection)))
    df_inj_piez = df_inj_piez[df_inj_piez.number > 0]
    df_prod.insert(loc=df_prod.shape[1], column="intersection",
                   value=list(map(lambda x: check_intersection_point(x, df_inj_piez),
                                  df_prod.GEOMETRY)))
    df_prod.insert(loc=df_prod.shape[1], column="number",
                   value=list(map(lambda x: len(x), df_prod.intersection)))
    return df_prod, df_inj_piez


def optimization(df_prod, df_inj_piez):
    """
    Выделяется список нагнетательных/пьезометров из DataFrame продуктивных,
    имеющих 1 пересечение. Оптимизация заключается в переопределении
    списка нагн/пьез. с помощью исключения скважин, входящих
    как в список пересечений, так и в список исключений, из df_optim
    :param df_prod: DataFrame добывающих скважин
    :param df_inj_piez: DataFrame нагнетательных/пьезометров
    :return:
    """
    list_inj_piez_wells = []
    # выделяем пьезометры/нагнеталки, у которых есть только 1 пересечение
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
        #  создаем список уникальных значений столбца с пересечениями и сортируем по кол-ву пересечений
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


def add_shapely_types(df_input, mean_radius):
    """
    Добавление в DataFrame столбца с площадью охвата скважин, в зависимости от среднего радиуса охвата по контуру
    :param df_input: DataFrame, полученный из исходного файла
    :param mean_radius: средний радиус окружения для итерируемого объекта
    :return: Возвращается DataFrame с добавленными столбцами геометрии и площади влияния каждой скважины
    """
    if 'AREA' not in df_input:
        df_input.insert(loc=df_input.shape[1], column="AREA", value=0)

    df_input["AREA"] = df_input["AREA"].where(
        df_input["well type"] != "vertical", list(map(lambda x, y: get_polygon_well(
            mean_radius, "vertical", x, y), df_input.coordinateX, df_input.coordinateY)))
    df_input["AREA"] = df_input["AREA"].where(df_input["well type"] != "horizontal",
                                              list(map(lambda x, y, x1, y1:
                                                       get_polygon_well(
                                                           mean_radius, "horizontal", x, y, x1, y1),
                                                       df_input.coordinateX,
                                                       df_input.coordinateY,
                                                       df_input.coordinateX3,
                                                       df_input.coordinateY3)))
    return df_input


def write_to_excel(dict_result, list_columns, dict_constant):
    """
    Для записи результата расчетов в Excel подается словарь
    Для каждого ключа создается отдельный лист в документе
    :param dict_result: словарь, по ключам которого содержатся DataFrame для каждого контура
    :return: функция сохраняет файл в указанную директорию
    """
    app1 = xw.App(visible=False)
    new_wb = xw.Book()

    for key in dict_result.keys():
        name = str(key).replace("/", " ")
        if f"{name}" in new_wb.sheets:
            xw.Sheet[f"{name}"].delete()
        new_wb.sheets.add(f"{name}")
        sht = new_wb.sheets(f"{name}")
        df = dict_result[key]
        df["intersection"] = list(map(lambda x: " ".join(str(y) for y in x), df["intersection"]))
        del df["POINT"]
        del df["POINT3"]
        del df["GEOMETRY"]
        del df["AREA"]
        sht.range('A1').options().value = df
    df_report = get_report(dict_result, list_columns, dict_constant)
    if "report" in new_wb.sheets:
        xw.Sheet["report"].delete()
    new_wb.sheets.add("report")
    sht = new_wb.sheets("report")
    sht.range('A1').options().value = df_report
    new_wb.save("output\out_file_2.xlsx")
    # End print
    app1.kill()
    pass


def get_report(dict_result, list_columns, dict_constant):
    """
    :param dict_result: словарь с результатами расчетов по всем объектам
    :param list_columns: список названий столбцов для подготовки отчетного DataFrame
    :param dict_constant: словарь со статусами скважин
    :return: возвращает DataFrame с отчетом по каждому контуру с определенным коэффициентом домножения радиуса
    """
    df_report = pd.DataFrame(columns=list_columns)
    PROD_STATUS, PROD_MARKER, PIEZ_STATUS, INJ_MARKER, INJ_STATUS = unpack(dict_constant)
    for key in dict_result:
        df = dict_result[key]
        contour_k = key
        obj = set(df['workHorizon'].explode().unique())
        mean_rad = df['mean_radius'].mean()
        mean_time = df['research_time'].mean()
        df_prod = df.loc[(df.workMarker == PROD_MARKER) & (df.wellStatus.isin(PROD_STATUS))]
        df_piez = df.loc[df.wellStatus == PIEZ_STATUS]
        df_inj = df.loc[(df.workMarker == INJ_MARKER) & (df.wellStatus.isin(INJ_STATUS))]
        well_quantity = df.shape[0]
        research_wells = set(df['intersection'].explode().unique())

        df_report.loc[len(df_report.index)] = [contour_k, len(obj), mean_rad, mean_time, len(df_piez), len(df_inj),
                                               len(df_prod), well_quantity, len(research_wells),
                                               df['oil_loss'].sum(), df['injection_loss'].sum()]
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
    :param path: путь к файлу с параметрами
    :param well_name: имя скважины
    :param df_result: DataFrame с данными по контуру
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
    time_coef = 462.2824 * (mu * ct * phi / k) / len(list_obj)
    return time_coef
