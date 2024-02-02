import os

import geopandas as gpd
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
from loguru import logger
from matplotlib.lines import Line2D
from tqdm import tqdm

from geometry import check_intersection_area


def clean_pictures_folder(path):
    """
    Функция очищает папку с рисунками предыдущего расчета
    :param path: путь к папке с рисунками
    :return: не возвращает объектов, удаляет содержимое папки
    """
    for f in os.listdir(path):
        os.remove(os.path.join(path, f))
    pass


def visualization(df_input_prod, percent, dict_result):
    """
    Функция визуализации полученных результатов
    :param percent: процент длины траектории скважины, при котором она попадает в контур
    :param df_input_prod: DataFrame продуктивных скважин из исходного файла
    :param dict_result: словарь для записи результатов
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
        if df_result.empty:
            continue
        list_objects = df_result.workHorizon.str.split(', ').explode().unique()

        for horizon in tqdm(list_objects, "Mapping for objects", position=0, leave=True, colour='white'):
            hor_prod_wells = df_input_prod[
                list(map(lambda x: len(set(x.replace(" ", "").split(",")) & set([horizon])) > 0,
                         df_input_prod.workHorizon))]
            try:
                contour_prod_wells = hor_prod_wells[hor_prod_wells.wellName.isin(
                    set(check_intersection_area(polygon, hor_prod_wells, percent, calc_option=True)))]
            except TypeError:
                # из всего загруженного добывающего фонда отбираются скважины из столбца пересечений df_result, а также
                # идет отбор по текущему объекту
                contour_prod_wells = hor_prod_wells[
                    hor_prod_wells["wellName"].isin(list(
                        set(df_result[df_result['current_horizon'] == horizon]["intersection"].explode().unique())))]
            df_current_calc = df_result.loc[df_result.current_horizon == horizon]
            # division production wells on two parts
            list_exception = list(set(
                df_current_calc[df_current_calc['intersection'].map(str) == 'Не охвачены исследованием!!!'].wellName))
            contour_prod_nonexception = list(set(contour_prod_wells.wellName.explode().unique()).difference(
                set(list_exception)))
            contour_prod_exception = list(set(contour_prod_wells.wellName.explode().unique())
                                          .intersection(set(list_exception)))
            df_prod_nonexception = contour_prod_wells[contour_prod_wells['wellName'].isin(contour_prod_nonexception)]
            df_prod_exception = contour_prod_wells[contour_prod_wells['wellName'].isin(contour_prod_exception)]

            if df_current_calc.empty:
                continue

            else:
                mean_radius = df_current_calc.iloc[0]['mean_radius']
            # задание типов линий по годам исследования
            type_lines = {0: "-", 1: ":", 2: "-."}
            colors_piez = {0: "darkgreen", 1: "green", 2: "limegreen"}
            colors_inj = {0: "lightseagreen", 1: "turquoise", 2: "lightskyblue"}
            colors_prod = {0: "orangered", 1: "tomato", 2: "coral"}
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

                # geodataframe
                gdf_measuring_wells = gpd.GeoDataFrame(df_current_year)
                gdf_piez = gdf_measuring_wells.loc[gdf_measuring_wells['fond'] == 'ПЬЕЗ']
                gdf_inj = gdf_measuring_wells.loc[gdf_measuring_wells['fond'] == 'НАГ']
                gdf_prod = gdf_measuring_wells.loc[gdf_measuring_wells['fond'] == 'ДОБ']
                if year == 0:
                    ax = gpd.GeoSeries(gdf_piez.AREA).plot(color="springgreen", figsize=[20, 20])
                else:
                    # Piezometric well areas drawing
                    gpd.GeoSeries(gdf_piez.AREA).plot(ax=ax, color="springgreen")
                gpd.GeoSeries(gdf_piez.AREA).boundary.plot(ax=ax, ls=type_lines[year],
                                                           color=colors_piez[year])

                # production well areas drawing
                gpd.GeoSeries(gdf_prod[~(gdf_prod['wellName'].isin(list_exception))]["AREA"]).plot(ax=ax,
                                                                                                   color="lightsalmon")
                gpd.GeoSeries(gdf_prod[~(gdf_prod['wellName'].isin(list_exception))]["AREA"]).boundary.plot(ax=ax, ls=
                type_lines[year],
                                                                                                            color=
                                                                                                            colors_prod[
                                                                                                                year])

                # Injection well areas drawing
                gpd.GeoSeries(gdf_inj["AREA"]).plot(ax=ax, color="azure")
                gpd.GeoSeries(gdf_inj["AREA"]).boundary.plot(ax=ax, ls=type_lines[year],
                                                             color=colors_inj[year])

                # Boundary contour
                gpd.GeoSeries(polygon).boundary.plot(ax=ax, color='saddlebrown')

            # Signature of piezometric wells
            gdf_measuring_all = gpd.GeoDataFrame(df_current_calc)
            for x, y, label in zip(gdf_measuring_all.coordinateX.values,
                                   gdf_measuring_all.coordinateY.values,
                                   gdf_measuring_all.wellName):
                ax.annotate(label, xy=(x, y), xytext=(3, 3), textcoords="offset points", color="red", fontsize=6)
            # Signature of production wells
            for x, y, label in zip(df_prod_nonexception.coordinateX.values,
                                   df_prod_nonexception.coordinateY.values,
                                   df_prod_nonexception.wellName):
                ax.annotate(label, xy=(x, y), xytext=(3, 3), textcoords="offset points", color="navy", fontsize=6)
            # Signature of excluded production wells
            if len(contour_prod_exception):
                for x, y, label in zip(df_prod_exception.coordinateX.values,
                                       df_prod_exception.coordinateY.values,
                                       df_prod_exception.wellName):
                    ax.annotate(label, xy=(x, y), xytext=(3, 3), textcoords="offset points", color="navy", fontsize=6)
            # Trajectory of wells
            contour_prod_wells = contour_prod_wells.set_geometry(contour_prod_wells["GEOMETRY"])
            contour_prod_wells.plot(ax=ax, color="black", markersize=14)
            gdf_measuring_all = gdf_measuring_all.set_geometry(df_result["GEOMETRY"])
            gdf_measuring_all.plot(ax=ax, color="blue", markersize=14, marker="^")

            # Black points is production, blue triangle is piezometric
            df_prod_nonexception = df_prod_nonexception.set_geometry(df_prod_nonexception["POINT"])
            df_prod_nonexception.plot(ax=ax, color="black", markersize=14)
            gdf_measuring_all = gdf_measuring_all.set_geometry(df_result["POINT"])
            gdf_measuring_all.plot(ax=ax, color="blue", markersize=14, marker="^")
            if len(contour_prod_exception):
                df_prod_exception = df_prod_exception.set_geometry(df_prod_exception["POINT"])
                df_prod_exception.plot(ax=ax, color="gray", markersize=14)
                df_prod_exception = df_prod_exception.set_geometry(df_prod_exception["GEOMETRY"])
                df_prod_exception.plot(ax=ax, color="gray", markersize=14, marker="^")

            piez = mpatches.Patch(color='black', fc='springgreen', label='Пьезометры')
            inj = mpatches.Patch(color='black', fc='azure', label='Нагнетательные')
            prod = mpatches.Patch(color='black', fc='lightsalmon', label='Добыващие(с исследованием)')
            piez_point = Line2D([0], [0], marker='^', color='white', label='Скважины опорной сети',
                                markerfacecolor='blue', markersize=14)
            prod_point = Line2D([0], [0], marker='.', color='white', label='Добывающий фонд',
                                markerfacecolor='black', markersize=14)
            prod_point_exception = Line2D([0], [0], marker='.', color='white', label='Не охвачены исследованием',
                                          markerfacecolor='gray', markersize=14)
            line_1_year = Line2D([0], [0], color='gray', linestyle="-", lw=1, label='Исследования на текущий год')
            line_2_year = Line2D([0], [0], color='gray', linestyle=":", lw=1, label='На 2 год')
            line_3_year = Line2D([0], [0], color='gray', linestyle="-.", lw=1, label='На 3 год')

            if polygon is None:
                plt.legend(
                    handles=[piez, inj, prod, piez_point, prod_point, prod_point_exception, line_1_year, line_2_year,
                             line_3_year])
                plt.savefig(
                    f'output/pictures/{horizon.replace('/', '_')}, out contour, R = {int(mean_radius)}, k = {mult_coef}.png',
                    dpi=200)
                plt.title(
                    f'Объект: {horizon.replace('/', '_')}, out contour, (R = {int(mean_radius)}, k = {mult_coef})')

            else:
                plt.legend(
                    handles=[piez, inj, prod, piez_point, prod_point, prod_point_exception, line_1_year, line_2_year,
                             line_3_year])
                plt.savefig(
                    f'output/pictures/{horizon.replace('/', '_')}, {contour_name}, R = {int(mean_radius)}, k = {mult_coef}.png',
                    dpi=200)
                plt.title(
                    f'Объект: {horizon.replace('/', '_')}, контур: {contour_name}, (R = {int(mean_radius)}, k = {mult_coef})')

    pass
