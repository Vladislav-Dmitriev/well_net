import geopandas as gpd
import pandas as pd
from shapely.geometry import LineString, Point, Polygon


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
    имена скважин из другого DataFrame, с которыми пересекается текущая, затем добавляется столбец 'number',
    в который заносится кол-во пересечений конкретной скважины с остальными
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
                                       df_prod.GEOMETRY))
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
