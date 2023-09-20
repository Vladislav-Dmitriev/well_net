import geopandas as gpd
import matplotlib.pyplot as plt
from functions import unpack


def visualisation(polygon, contour_name, horizon, mean_radius, mult_coef, df_result, df_prod_wells, **dict_constant):
    '''
    Функция визуализации полученных результатов
    :param polygon: Геометрический объект GeoPandas, созданный из координат контура,
    подается для построения границы контура
    :param contour_name: Геометрический объект GeoPandas, полученный из координат контура, подающегося в программу
    :param horizon: Название файла с координатами текущего контура без расширения файла
    :param mean_radius: Значение радиуса первого ряда для текущего контура
    :param df_result: Промежуточный DataFrame, посчитанный для одного объекта
    :param df_prod_wells: DataFrame добывающих скважин
    :param dict_constant: Словарь с характером работы и состоянием скажины
    :return: Сохраняет график, построенный по итерируемому объекту, в указанную директорию
    '''
    # for key in dict_result.keys():
    PROD_STATUS, PROD_MARKER, PIEZ_STATUS, INJ_MARKER, INJ_STATUS = unpack(dict_constant)
    hor_prod_wells = df_prod_wells[list(map(lambda x: len(set(x.replace(" ", "").split(","))) > 0,
                                            df_prod_wells.workHorizon))]

    # geodataframe
    gdf_measuring_wells = gpd.GeoDataFrame(df_result)
    gdf_piez = gdf_measuring_wells.loc[gdf_measuring_wells.wellStatus == PIEZ_STATUS]
    gdf_inj = gdf_measuring_wells.loc[(gdf_measuring_wells.workMarker == INJ_MARKER)
                                      & (gdf_measuring_wells.wellStatus.isin(INJ_STATUS))]
    gdf_prod = gdf_measuring_wells.loc[(gdf_measuring_wells.workMarker == PROD_MARKER)
                                       & (gdf_measuring_wells.wellStatus.isin(PROD_STATUS))]

    if polygon is None:
        # Piezometric well areas drawing
        ax = gpd.GeoSeries(gdf_piez.AREA).plot(color="lightsalmon", figsize=[20, 20])
        gpd.GeoSeries(gdf_piez.AREA).boundary.plot(ax=ax, color="orangered")

        # Signature of piezometric wells
        for x, y, label in zip(gdf_measuring_wells.coordinateX.values,
                               gdf_measuring_wells.coordinateY.values,
                               gdf_measuring_wells.wellName):
            ax.annotate(label, xy=(x, y), xytext=(3, 3), textcoords="offset points", color="red", fontsize=6)
        # Signature of production wells
        for x, y, label in zip(hor_prod_wells.coordinateX.values,
                               hor_prod_wells.coordinateY.values,
                               hor_prod_wells.wellName):
            ax.annotate(label, xy=(x, y), xytext=(3, 3), textcoords="offset points", color="navy",
                        fontsize=6)

        # production well areas drawing
        gpd.GeoSeries(gdf_prod["AREA"]).plot(ax=ax, color="springgreen")
        gpd.GeoSeries(gdf_prod["AREA"]).boundary.plot(ax=ax, color="seagreen")

        # Injection well areas drawing
        gpd.GeoSeries(gdf_inj["AREA"]).plot(ax=ax, color="paleturquoise")
        gpd.GeoSeries(gdf_inj["AREA"]).boundary.plot(ax=ax, color="lightseagreen")

        # Black points is production, blue triangle is piezometric
        gdf_measuring_wells = gdf_measuring_wells.set_geometry(df_result["POINT"])
        gdf_measuring_wells.plot(ax=ax, color="blue", markersize=13, marker="^")
        hor_prod_wells = hor_prod_wells.set_geometry(hor_prod_wells["POINT"])
        hor_prod_wells.plot(ax=ax, color="black", markersize=13)

        # Trajectory of wells
        gdf_measuring_wells = gdf_measuring_wells.set_geometry(df_result["GEOMETRY"])
        gdf_measuring_wells.plot(ax=ax, color="blue", markersize=13, marker="^")
        hor_prod_wells = hor_prod_wells.set_geometry(hor_prod_wells["GEOMETRY"])
        hor_prod_wells.plot(ax=ax, color="black", markersize=13)

        # Boundary contour
        # gpd.GeoSeries(polygons).boundary.plot(ax=ax, color='saddlebrown')

        plt.savefig(f'output/pictures/{horizon},out contour, R = {int(mean_radius)}, k = {mult_coef}.png', dpi=200, quality=100)
        plt.title(f'Объект: + {horizon}, out contour, (R = {int(mean_radius)}, k = {mult_coef})')
        # plt.show()

    else:
        # Piezometric well areas drawing
        ax = gpd.GeoSeries(gdf_piez.AREA).plot(color="lightsalmon", figsize=[20, 20])
        gpd.GeoSeries(gdf_piez.AREA).boundary.plot(ax=ax, color="orangered")

        # Signature of piezometric wells
        for x, y, label in zip(gdf_measuring_wells.coordinateX.values,
                               gdf_measuring_wells.coordinateY.values,
                               gdf_measuring_wells.wellName):
            ax.annotate(label, xy=(x, y), xytext=(3, 3), textcoords="offset points", color="red", fontsize=6)
        # Signature of production wells
        for x, y, label in zip(hor_prod_wells.coordinateX.values,
                               hor_prod_wells.coordinateY.values,
                               hor_prod_wells.wellName):
            ax.annotate(label, xy=(x, y), xytext=(3, 3), textcoords="offset points", color="navy", fontsize=6)

        # production well areas drawing
        gpd.GeoSeries(gdf_prod["AREA"]).plot(ax=ax, color="springgreen")
        gpd.GeoSeries(gdf_prod["AREA"]).boundary.plot(ax=ax, color="seagreen")

        # Injection well areas drawing
        gpd.GeoSeries(gdf_inj["AREA"]).plot(ax=ax, color="paleturquoise")
        gpd.GeoSeries(gdf_inj["AREA"]).boundary.plot(ax=ax, color="lightseagreen")

        # Black points is production, blue triangle is piezometric
        gdf_measuring_wells = gdf_measuring_wells.set_geometry(df_result["POINT"])
        gdf_measuring_wells.plot(ax=ax, color="blue", markersize=13, marker="^")
        hor_prod_wells = hor_prod_wells.set_geometry(hor_prod_wells["POINT"])
        hor_prod_wells.plot(ax=ax, color="black", markersize=13)

        # Trajectory of wells
        gdf_measuring_wells = gdf_measuring_wells.set_geometry(df_result["GEOMETRY"])
        gdf_measuring_wells.plot(ax=ax, color="blue", markersize=13, marker="^")
        hor_prod_wells = hor_prod_wells.set_geometry(hor_prod_wells["GEOMETRY"])
        hor_prod_wells.plot(ax=ax, color="black", markersize=13)

        # Boundary contour
        gpd.GeoSeries(polygon).boundary.plot(ax=ax, color='saddlebrown')

        plt.savefig(f'output/pictures/{horizon},{contour_name}, R = {int(mean_radius)}, k = {mult_coef}.png',
                    dpi=200, quality=100)
        plt.title(f'Объект: {horizon}, контур: {contour_name}, (R = {int(mean_radius)}, k = {mult_coef})')
        # plt.show()
    pass
