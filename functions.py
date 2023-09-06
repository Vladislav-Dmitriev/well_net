from shapely.geometry import LineString, Point
import geopandas as gpd
import xlwings as xw


def get_polygon_well(R_well, type_well, *coordinates):
    '''
    Создание зоны вокруг скважины с заданным радиусом
    :param R_well: радиус создания зоны
    :param type_well: тип скважины
    :param coordinates: координаты устье/забой
    :return: возвращает геометрический объект зоны вокруг скважины
    '''
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
    '''
    Проверка входят ли скважины из df_point в зону другой скважины area
    :param area: координаты зоны вокруг конкретной скважины
    :param df_points: данные из которых берется геометрия скважин(точки/линии)
    :return: возвращаются имена скважин, которые входят в данную зону area
    '''
    df_points = gpd.GeoDataFrame(df_points, geometry="GEOMETRY")
    df_points = df_points[df_points["GEOMETRY"].intersects(area)]
    return df_points.wellNumberColumn.values


def unpack(dict_constant):
    '''
    Распаковка параметров из словаря, для удобства использования в коде
    :param dict_constant: словарь со статусами скважин и характером их работы
    :return: возвращает статусы и характер работы скважин как отдельные переменные типа string
    '''
    return dict_constant.get("PROD_STATUS"), dict_constant.get("PROD_MARKER"), dict_constant.get("PIEZ_STATUS"),\
            dict_constant.get("INJ_MARKER"), dict_constant.get("INJ_STATUS")


def check_intersection_point(point, df_areas):
    '''
    Функция позволяет узнать, перечесение со сколькими зонами имеет определенная скважина
    :param point: геометрия скважины(точка/линия)
    :param df_areas: DataFrame со столбцом зон вокруг скважин
    :return: перечесение со сколькими зонами имеет определенная скважина
    '''
    df_areas = gpd.GeoDataFrame(df_areas, geometry="AREA")
    df_areas = df_areas[df_areas["AREA"].intersects(point)]
    return df_areas.wellNumberColumn.values


def intersect_number(df_prod, df_inj_piez):
    '''
    Функция добавляет в DataFrame столбец 'intersection', в него записываются
    имена скважин, с которыми пересекается текущая, затем добавляется
    столбец 'number', в который заносится кол-во пересечений конкретной скважины с остальными
    :param df_prod: добывающие
    :param df_inj_piez: нагнетательные/пьезометры
    :return: возвращаются DataFrame с кол-вом пересечений
    '''
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
    '''
    Выделяется список нагнетательных/пьезометров из DataFrame продуктивных,
    имеющих 1 пересечение. Оптимизация заключается в переопределении
    списка нагн/пьез. с помощью исключения скважин, входящих
    как в список пересечений, так и в список исключений, из df_optim
    :param df_prod: DataFrame добывающих скважин
    :param df_inj_piez: DataFrame нагнетательных/пьезометров
    :return:
    '''
    list_inj_piez_wells = []
    # выделяем пьезометры/нагнеталки, у которых есть только 1 пересечение
    list_inj_piez_wells += list(df_prod[df_prod.number == 1].intersection.explode().unique())
    list_prod_wells = df_inj_piez[
        df_inj_piez.wellNumberColumn.isin(list_inj_piez_wells)].intersection.explode().unique()
    # создаем dataframe оптимизации, исключая скважины с одним пересечением
    df_optim = df_inj_piez[~df_inj_piez.wellNumberColumn.isin(list_inj_piez_wells)]
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
        for well in df_optim.wellNumberColumn.values:
            set_exception = set(df_optim[df_optim.wellNumberColumn != well].intersection.explode().unique())
            # при совпадении наборов исключений и пересечений из df_optim исключается итерируемая скважина
            # и добавляется к списку нагн./пьез.
            if set_exception == set_visible_wells:
                df_optim = df_optim[df_optim.wellNumberColumn != well]
        list_inj_piez_wells += list(df_optim.wellNumberColumn.values)

    return list_inj_piez_wells


def write_to_excel(dict_result):
    '''
    Для записи результата расчетов в Excel подается словарь
    Для каждого ключа создается отдельный лист в документе
    :param dict_result: словарь, по ключам которого содержатся DataFrame для каждого контура
    :return: функция сохраняет файл в указанную директорию
    '''
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

    new_wb.save("output\out_file_2.xlsx")
        # sht.range('A1').options().value = df
        # sht_out.range('A1').options().value = wells_out_contour

    # new_wb.save("output\out_file.xlsx")
    # End print
    app1.kill()
    pass



