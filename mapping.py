import geopandas as gpd
import matplotlib.pyplot as plt
from shapely.geometry import Polygon
import pandas as pd
from functions import check_intersection_area, check_intersection_point


def visualisation(polygon, contour_name, df_result, df_prod_wells, fontsize, point_size, *status):

    # for key in result.keys():
    hor_prod_wells = df_prod_wells[list(map(lambda x: len(set(x.replace(" ", "").split(","))) > 0,
                                            df_prod_wells.workHorizon))]

    gdf_measuring_wells = gpd.GeoDataFrame(df_result)

    gdf_piez = gdf_measuring_wells.loc[gdf_measuring_wells.wellStatus == status[2]]
    gdf_inj = gdf_measuring_wells.loc[(gdf_measuring_wells.workMarker == status[3])
                                      & (gdf_measuring_wells.wellStatus.isin(status[4]))]
    gdf_prod = gdf_measuring_wells.loc[(gdf_measuring_wells.workMarker == status[0])
                                       & (gdf_measuring_wells.wellStatus.isin(status[1]))]

    # Piezometric well areas drawing
    ax = gpd.GeoSeries(gdf_piez.AREA).plot(color="lightsalmon", figsize=[20, 20])
    gpd.GeoSeries(gdf_piez.AREA).boundary.plot(ax=ax, color="orangered")

    # Signature of piezometric wells
    for x, y, label in zip(gdf_measuring_wells.coordinateX.values,
                           gdf_measuring_wells.coordinateY.values,
                           gdf_measuring_wells.wellNumberColumn):
        ax.annotate(label, xy=(x, y), xytext=(3, 3), textcoords="offset points", color="red", fontsize=fontsize)
    # Signature of production wells
    for x, y, label in zip(hor_prod_wells.coordinateX.values,
                           hor_prod_wells.coordinateY.values,
                           hor_prod_wells.wellNumberColumn):
        ax.annotate(label, xy=(x, y), xytext=(3, 3), textcoords="offset points", color="navy", fontsize=fontsize)

    # Black points is production, blue triangle is piezometric
    gdf_measuring_wells = gdf_measuring_wells.set_geometry(gdf_measuring_wells["GEOMETRY"])
    gdf_measuring_wells.plot(ax=ax, color="blue", markersize=point_size, marker="^")
    hor_prod_wells = hor_prod_wells.set_geometry(hor_prod_wells["GEOMETRY"])
    hor_prod_wells.plot(ax=ax, color="black", markersize=point_size)

    # production well areas drawing
    gpd.GeoSeries(gdf_prod["AREA"]).plot(ax=ax, color="springgreen")
    gpd.GeoSeries(gdf_prod["AREA"]).boundary.plot(ax=ax, color="seagreen")

    # Injection well areas drawing
    gpd.GeoSeries(gdf_inj["AREA"]).plot(ax=ax, color="paleturquoise")
    gpd.GeoSeries(gdf_inj["AREA"]).boundary.plot(ax=ax, color="lightseagreen")

    # Boundary contour
    gpd.GeoSeries(polygon).boundary.plot(ax=ax, color='k')

    plt.savefig('output/pictures/' + str(contour_name).replace("/", " ") + '.png', dpi=200, quality=100)
    plt.show()
    plt.clf()
    pass