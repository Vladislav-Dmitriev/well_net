from shapely.geometry import LineString, Point
import geopandas as gpd


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
    df_points = gpd.GeoDataFrame(df_points, geometry="POINT")
    df_points = df_points[df_points["POINT"].intersects(area)]
    return df_points.wellNumberColumn.values


def check_intersection_point(point, df_areas):
    df_areas = gpd.GeoDataFrame(df_areas, geometry="AREA")
    df_areas = df_areas[df_areas["AREA"].intersects(point)]
    return df_areas.wellNumberColumn.values


# def add_shapely_types(coordX, coordY, coordX3, coordY3, df_wells):
#     df_wells.insert(loc=df_wells.shape[1], column="POINT",
#                           value=list(map(lambda x, y: Point(x, y),
#                                          df_wells.coordX,
#                                          df_wells.coordY)))
#     df_wells.insert(loc=df_wells.shape[1], column="POINT3",
#                     value=list(map(lambda x, y: Point(x, y),
#                                    df_wells.coordX3,
#                                    df_wells.coordY3)))
#     df_wells.insert(loc=df_wells.shape[1], column="AREA",
#                          value=list(
#                              map(lambda x, y, x1, y1: get_polygon_well(R_well, type_well, *coordinates),
#                                  hor_inj_wells.coordinateX, hor_inj_wells.coordinateY, hor_inj_wells.coordinateX3,
#                                  hor_inj_wells.coordinateY3)))