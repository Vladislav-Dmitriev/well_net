from shapely.geometry import LineString, Point, Polygon
import geopandas as gpd
import xlwings as xw


def get_polygon_well(R_well, type_well, *coordinates):
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
    df_points = gpd.GeoDataFrame(df_points, geometry="GEOMETRY")
    df_points = df_points[df_points["GEOMETRY"].intersects(area)]
    return df_points.wellNumberColumn.values

def check_intersection_point(point, df_areas):
    df_areas = gpd.GeoDataFrame(df_areas, geometry="AREA")
    df_areas = df_areas[df_areas["AREA"].intersects(point)]
    return df_areas.wellNumberColumn.values

def intersect_number(df_prod, df_inj_piez):
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
    list_inj_piez_wells = []
    list_inj_piez_wells += list(df_prod[df_prod.number == 1].intersection.explode().unique())
    list_prod_wells = df_inj_piez[
        df_inj_piez.wellNumberColumn.isin(list_inj_piez_wells)].intersection.explode().unique()

    df_optim = df_inj_piez[~df_inj_piez.wellNumberColumn.isin(list_inj_piez_wells)]
    df_optim.intersection = list(
        map(lambda x: list(set(x).difference(set(list_prod_wells))), df_optim.intersection))
    df_optim.number = list(map(lambda x: len(x), df_optim.intersection))
    df_optim = df_optim[df_optim.number > 0]

    if not df_optim.empty:
        set_visible_wells = set(df_optim.intersection.explode().unique())
        df_optim = df_optim.sort_values(by=['number'], ascending=True)
        for well in df_optim.wellNumberColumn.values:
            set_exception = set(df_optim[df_optim.wellNumberColumn != well].intersection.explode().unique())
            if set_exception == set_visible_wells:
                df_optim = df_optim[df_optim.wellNumberColumn != well]
        list_inj_piez_wells += list(df_optim.wellNumberColumn.values)

    return list_inj_piez_wells

def write_to_excel(new_wb, result, contour_name):
    # Start print in Excel
    new_wb.sheets.add('')
    for key in result.keys():
        name = str(key).replace("/", " ")
        if f"{name}" in new_wb.sheets:
            xw.Sheet[f"{name}"].delete()
        new_wb.sheets.add(f"{name}")
        sht = new_wb.sheets(f"{name}")
        df = result[key]
        df["intersection"] = list(
            map(lambda x: " ".join(str(y) for y in x), df["intersection"]))
        del df["POINT"]
        del df["POINT3"]
        del df["GEOMETRY"]
        del df["AREA"]
        sht.range('A1').options().value = df

    new_wb.save("output\out_file.xlsx")
    app1.kill()
    # End print
    pass



