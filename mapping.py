import geopandas as gpd
import matplotlib.pyplot as plt
from loguru import logger
from tqdm import tqdm

from functions import unpack_status, clean_pictures_folder, check_intersection_area


def visualization(df_input_prod, percent, dict_result, **dict_constant):
    """
    Функция визуализации полученных результатов
    :param percent: процент длины траектории скважины, при котором она попадает в контур
    :param df_input_prod: DataFrame продуктивных скважин из исходного файла
    :param dict_result: словарь для записи результатов
    :param dict_constant: Словарь с характером работы и состоянием скважины
    :return: Сохраняет график, построенный по итерируемому объекту, в указанную директорию
    """
    # удаление старых графиков
    logger.info("Clean pictures folder")
    clean_pictures_folder('output/pictures/')

    for key, value in dict_result.items():
        mult_coef = float(list(key.replace(' = ', ', ').split(', '))[2])
        contour_name = list(key.replace(' = ', ', ').split(', '))[0]
        logger.info(f'Plot for {contour_name} with k = {mult_coef}')

        polygon = value[1]
        df_result = value[0]
        list_objects = df_result.workHorizon.str.split(', ').explode().unique()

        for horizon in tqdm(list_objects, "Mapping for objects", position=0, leave=False, ncols=80):
            PROD_STATUS, PROD_MARKER, PIEZ_STATUS, INJ_MARKER, INJ_STATUS = unpack_status(dict_constant)
            hor_prod_wells = df_input_prod[
                list(map(lambda x: len(set(x.replace(" ", "").split(",")) & set([horizon])) > 0,
                         df_input_prod.workHorizon))]
            try:
                contour_prod_wells = hor_prod_wells[hor_prod_wells.wellName.isin(
                    set(check_intersection_area(polygon, hor_prod_wells, percent, calc_option=True)))]
                # contour_prod_wells = hor_prod_wells[hor_prod_wells["GEOMETRY"].isin(list_wells_in_contour)]
            except TypeError:
                contour_prod_wells = hor_prod_wells[
                    hor_prod_wells["wellName"].isin(list(set(df_result["intersection"].explode().unique())))]
            df_current_calc = df_result.loc[df_result.current_horizon == horizon]

            if df_current_calc.empty:
                continue

            else:
                mean_radius = df_current_calc.iloc[0]['mean_radius']
            # задание типов линий по годам исследования
            type_lines = {0: "-", 1: ":", 2: "-."}
            legend_labels = {0: "Текущий год", 1: "1 год", 2: "2 год"}
            colors_piez = {0: "orangered", 1: "tomato", 2: "coral"}
            colors_inj = {0: "lightseagreen", 1: "turquoise", 2: "lightskyblue"}
            colors_prod = {0: "darkgreen", 1: "green", 2: "limegreen"}
            years_list = [0]
            if mult_coef > 1.5:
                years_list += [1, 2]
            for year in years_list:
                try:
                    df_current_year = df_current_calc[df_current_calc['year_of_survey'] == year]
                    if df_current_year.empty:
                        continue
                except KeyError:
                    df_current_year = df_current_calc

                if df_current_year.empty:
                    continue

                type_line = type_lines[year]
                # geodataframe
                gdf_measuring_wells = gpd.GeoDataFrame(df_current_year)
                gdf_piez = gdf_measuring_wells.loc[gdf_measuring_wells.wellStatus == PIEZ_STATUS]
                gdf_inj = gdf_measuring_wells.loc[(gdf_measuring_wells.workMarker == INJ_MARKER)
                                                  & (gdf_measuring_wells.wellStatus.isin(INJ_STATUS))]
                gdf_prod = gdf_measuring_wells.loc[(gdf_measuring_wells.workMarker == PROD_MARKER)
                                                   & (gdf_measuring_wells.wellStatus.isin(PROD_STATUS))]
                if year == 0:
                    ax = gpd.GeoSeries(gdf_piez.AREA).plot(color="lightsalmon", figsize=[20, 20])
                else:
                    # Piezometric well areas drawing
                    gpd.GeoSeries(gdf_piez.AREA).plot(ax=ax, color="lightsalmon")
                gpd.GeoSeries(gdf_piez.AREA).boundary.plot(ax=ax, ls=type_lines[year],
                                                           label=f'{legend_labels[year]} для исследуемых скважин',
                                                           color=colors_piez[year])

                # Signature of piezometric wells
                for x, y, label in zip(gdf_measuring_wells.coordinateX.values,
                                       gdf_measuring_wells.coordinateY.values,
                                       gdf_measuring_wells.wellName):
                    ax.annotate(label, xy=(x, y), xytext=(3, 3), textcoords="offset points", color="red", fontsize=6)
                # Signature of production wells
                for x, y, label in zip(contour_prod_wells.coordinateX.values,
                                       contour_prod_wells.coordinateY.values,
                                       contour_prod_wells.wellName):
                    ax.annotate(label, xy=(x, y), xytext=(3, 3), textcoords="offset points", color="navy", fontsize=6)

                # production well areas drawing
                gpd.GeoSeries(gdf_prod["AREA"]).plot(ax=ax, color="springgreen")
                gpd.GeoSeries(gdf_prod["AREA"]).boundary.plot(ax=ax, ls=type_lines[year],
                                                              label=f'{legend_labels[year]} для добывающих скважин',
                                                              color=colors_prod[year])

                # Injection well areas drawing
                gpd.GeoSeries(gdf_inj["AREA"]).plot(ax=ax, color="azure")
                gpd.GeoSeries(gdf_inj["AREA"]).boundary.plot(ax=ax, ls=type_lines[year],
                                                             label=f'{legend_labels[year]} для нагнетательных скважин',
                                                             color=colors_inj[year])

                # Trajectory of wells
                gdf_measuring_wells = gdf_measuring_wells.set_geometry(df_result["GEOMETRY"])
                gdf_measuring_wells.plot(ax=ax, color="blue", markersize=14, marker="^")
                contour_prod_wells = contour_prod_wells.set_geometry(contour_prod_wells["GEOMETRY"])
                contour_prod_wells.plot(ax=ax, color="black", markersize=14)

                # Black points is production, blue triangle is piezometric
                gdf_measuring_wells = gdf_measuring_wells.set_geometry(df_result["POINT"])
                gdf_measuring_wells.plot(ax=ax, color="blue", markersize=14, marker="^")
                contour_prod_wells = contour_prod_wells.set_geometry(contour_prod_wells["POINT"])
                contour_prod_wells.plot(ax=ax, color="black", markersize=14)

                # Boundary contour
                gpd.GeoSeries(polygon).boundary.plot(ax=ax, color='saddlebrown')

            if polygon is None:
                plt.legend()
                plt.savefig(f'output/pictures/{horizon}, out contour, R = {int(mean_radius)}, k = {mult_coef}.png',
                            dpi=200)
                plt.title(f'Объект: {horizon}, out contour, (R = {int(mean_radius)}, k = {mult_coef})')
                # plt.show()
                # plt.clf()
            else:
                plt.legend()
                plt.savefig(f'output/pictures/{horizon}, {contour_name}, R = {int(mean_radius)}, k = {mult_coef}.png',
                            dpi=200)
                plt.title(f'Объект: {horizon}, контур: {contour_name}, (R = {int(mean_radius)}, k = {mult_coef})')
                # plt.show()
                # plt.clf()
    pass
