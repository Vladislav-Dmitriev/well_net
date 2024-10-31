import os
import time

from tqdm import tqdm

import numpy as np
from loguru import logger
import geopandas as gpd
from shapely.geometry import LineString, Point, Polygon, MultiPolygon


@logger.catch(level='DEBUG')
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
        raise NameError(f'Wrong well type: {type_well}. Allowed values: vertical or horizontal')


@logger.catch(level='ERROR')
def check_intersection_area(area, df_points, percent, calc_option):
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


@logger.catch(level='DEBUG')
def check_intersection_point(point, df_areas, percent, calc_option):
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


@logger.catch(level='DEBUG')
def intersect_number(df_prod, df_inj_piez, percent, calc_option):
    """
    Функция добавляет в DataFrame столбец 'intersection', в него записываются
    имена скважин из другого DataFrame, с которыми пересекается текущая, затем добавляется столбец 'number',
    в который заносится кол-во пересечений конкретной скважины с остальными
    :param calc_option: параметр определяет критерий учета процента длины ГС для попадания в зону охвата
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

    df_inj_piez["intersection"] = list(map(lambda x: check_intersection_area(x, df_prod, percent, calc_option),
                                           df_inj_piez.AREA))
    df_inj_piez["number"] = df_inj_piez['intersection'].apply(lambda x: np.size(x))
    df_inj_piez = df_inj_piez[df_inj_piez.number > 0]
    df_prod["intersection"] = list(map(lambda x: check_intersection_point(x, df_inj_piez, percent, calc_option),
                                       df_prod.GEOMETRY))
    df_prod["number"] = df_prod['intersection'].apply(lambda x: np.size(x))
    return df_prod, df_inj_piez


@logger.catch(level='DEBUG')
def add_shapely_types(df_input, mean_rad, coeff):
    """
    Добавление в DataFrame столбца с площадью охвата скважин, в зависимости от среднего радиуса охвата по контуру
    :param coeff: коэффициент домножения радиуса
    :param df_input: DataFrame, полученный из исходного файла
    :param mean_rad: средний радиус окружения для итерируемого объекта
    :return: Возвращается DataFrame с добавленными столбцами геометрии и площади влияния каждой скважины
    """
    if 'AREA' not in df_input:
        df_input.insert(loc=df_input.shape[1], column="AREA", value=0)

    df_input["AREA"] = df_input["AREA"].where(
        df_input["well type"] != "vertical", list(map(lambda x, y: get_polygon_well(
            mean_rad * coeff, "vertical", x, y), df_input.coordinateX, df_input.coordinateY)))
    df_input["AREA"] = df_input["AREA"].where(df_input["well type"] != "horizontal",
                                              list(map(lambda x, y, x1, y1:
                                                       get_polygon_well(
                                                           mean_rad * coeff, "horizontal", x, y, x1, y1),
                                                       df_input.coordinateX,
                                                       df_input.coordinateY,
                                                       df_input.coordinateX3,
                                                       df_input.coordinateY3)))

    return df_input


@logger.catch(level='DEBUG')
def get_contours(contours_path, log_user, progress_bar):
    """
    Получение многоугольников контуров, заданных пользователем
    :param contours_path: абсолютный путь к .txt файлу с координатами контуров
    :param progress_bar: сигнал для изменения значения progress bar
    :param log_user: сигнал для вывода логов в окно для пользователя
    :return: словарь с многоугольниками, построенными из координат контруров, ключами словаря будут названия файлов
    """
    list_of_files = [f for f in os.listdir(path=contours_path) if f.endswith('.txt')]
    dict_contours = {}
    log_user.emit("Подготовка контуров")
    total_files_count = len(list_of_files)

    for current_file in tqdm(list_of_files, "Preparing contour coordinates", position=0, leave=True,
                             colour='white', ncols=80):
        with open(f'{contours_path}{current_file}', 'r') as file:
            data = list(filter(None, file.read().split('/')))
            list_polygons = []

            for i in range(len(data)):
                contour = [[float(y) for y in x.split(' ')] for x in list(filter(None, data[i].split('\n')))]
                list_polygons += [Polygon(contour)]
            exteriors = []
            holes = []

            for poly in list_polygons:
                hole_status = False

                for other in list_polygons:
                    if other == poly:
                        continue
                    if other.contains(poly):
                        hole_status = True
                        break

                if hole_status:
                    holes.append(poly)
                else:
                    exteriors.append(poly)

            multi_polygons = []
            for exterior in exteriors:
                interior_holes = [hole for hole in holes if exterior.contains(hole)]
                multi_polygons.append(
                    Polygon(exterior.exterior.coords, [hole.exterior.coords for hole in interior_holes]))

            dict_contours[f'{current_file.replace(".txt", "")}'] = MultiPolygon(multi_polygons)

        progress_bar.emit(int((list_of_files.index(current_file) + 1) / total_files_count * 100))

    return dict_contours
