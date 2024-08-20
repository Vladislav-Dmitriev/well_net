import os

import geopandas as gpd
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
from loguru import logger
from matplotlib.lines import Line2D
from shapely.ops import cascaded_union
from tqdm import tqdm

from src.calculation.geometry import check_intersection_area
from src.calculation.auxiliary_functions import get_path


@logger.catch(level='DEBUG')
def clean_pictures_folder(path):
    """
    Функция очищает папку с рисунками предыдущего расчета
    :param path: путь к папке с рисунками
    :return: не возвращает объектов, удаляет содержимое папки
    """
    logger.info("Clean pictures folder")
    for f in os.listdir(path):
        os.remove(os.path.join(path, f))
    pass


@logger.catch(level='DEBUG')
def visualization(df_input_prod, dict_result, percent, mean_oilrate_option):
    """
    Визуализация полученных результатов сценария с оптимальным охватом исследованиями добывающего фонда
    :param mean_oilrate_option: опция учета процента среднего дебита нефти по объекту
    :param percent: процент длины траектории скважины, при котором она попадает в контур
    :param df_input_prod: DataFrame продуктивных скважин из исходного файла
    :param dict_result: словарь с результатами расчета
    :return: Сохраняет график, построенный по итерируемому объекту, в указанную директорию
    """
    # удаление старых графиков
    application_path = get_path()
    clean_pictures_folder(f'{application_path}\\output\\optimize_mesh\\')

    logger.info('Begin plotting for 1 scenario')
    for key, value in dict_result.items():
        mult_coef = float(list(key.replace('=', ', ').split(', '))[-1])
        contour_name = list(key.replace(' = ', ', ').split(' k'))[0]
        logger.info(f'Plot for {contour_name} with k = {mult_coef}')

        polygon = value[1]
        df_result = value[0]

        list_objects = df_result.current_horizon.explode().unique()
        # list_objects = ['НП2-3']
        for horizon in tqdm(list_objects, "Mapping for objects", position=0, leave=True, colour='white'):
            hor_prod_wells = df_input_prod[
                list(map(lambda x: len(set(x.replace(" ", "").split(",")) & set([horizon])) > 0,
                         df_input_prod.workHorizon))]

            df_current_calc = df_result.loc[
                (df_result.current_horizon == horizon) & (df_result.fond != 'ПРОЕКТ') & (df_result.num_of_research < 2)]
            df_necessarily = df_result.loc[(df_result.current_horizon == horizon) & (df_result.num_of_research > 1)]
            # выделение DataFrame проектных скважин, тк охваченные исслед-ми проектные скважины содержатся в df_result
            df_research_project = df_result.loc[(df_result.current_horizon == horizon) & (df_result.fond == 'ПРОЕКТ')]
            df_nonresearch_proj = hor_prod_wells[(hor_prod_wells['fond'] == 'ПРОЕКТ') & (
                ~hor_prod_wells['wellName'].isin(list(df_research_project['wellName'].explode().unique())))]

            if polygon is not None:
                contour_prod_wells = hor_prod_wells[hor_prod_wells.wellName.isin(
                    set(check_intersection_area(polygon, hor_prod_wells, percent, calc_option=True)))]
                df_nonresearch_proj = contour_prod_wells[(contour_prod_wells['fond'] == 'ПРОЕКТ') & (
                    ~contour_prod_wells['wellName'].isin(list(df_research_project['wellName'].explode().unique())))]

            else:
                # из всего загруженного добывающего фонда отбираются скважины из столбца пересечений df_result, а также
                # идет отбор по текущему объекту расчета
                contour_prod_wells = hor_prod_wells[
                    hor_prod_wells["wellName"].isin(list(
                        set(df_result[df_result['current_horizon'] == horizon]["intersection"].explode().unique())))]

            if (df_current_calc.shape[0] != 0) and mean_oilrate_option:
                contour_prod_wells = contour_prod_wells.loc[
                    contour_prod_wells['oilRate'] <= df_current_calc['mean_oilrate'].iloc[0]]
            if df_current_calc.shape[0] != 0:
                contour_prod_wells = contour_prod_wells.loc[
                    contour_prod_wells['oilRate'] <= df_current_calc['limit_oilrate'].iloc[0]]

            # division production wells on two parts
            list_exception = list(set(
                df_current_calc[df_current_calc['intersection'].map(str) == 'Не охвачены исследованием!!!'].wellName))
            contour_prod_nonexception = list(set(contour_prod_wells.wellName.explode().unique()).difference(
                set(list_exception)))
            contour_prod_exception = list(set(contour_prod_wells.wellName.explode().unique())
                                          .intersection(set(list_exception)))
            df_prod_nonexception = contour_prod_wells[contour_prod_wells['wellName'].isin(contour_prod_nonexception)]
            df_prod_exception = contour_prod_wells[contour_prod_wells['wellName'].isin(contour_prod_exception)]

            if df_current_calc.empty and df_necessarily.empty:
                continue
            elif (not df_necessarily.empty) and df_current_calc.empty:
                mean_radius = df_necessarily.iloc[0]['mean_radius']
                gdf_necessarily = gpd.GeoDataFrame(df_necessarily)
                ax = gpd.GeoSeries(gdf_necessarily.AREA).plot(color="mistyrose", figsize=[20, 20])
                gpd.GeoSeries(gdf_necessarily.AREA).boundary.plot(ax=ax, color="indianred")

                # Signature of necessarily researched wells
                for x, y, label in zip(gdf_necessarily.coordinateX.values,
                                       gdf_necessarily.coordinateY.values,
                                       gdf_necessarily.wellName):
                    ax.annotate(label, xy=(x, y), xytext=(3, 3), textcoords="offset points", color="red", fontsize=6)
                gdf_necessarily = gdf_necessarily.set_geometry(gdf_necessarily["GEOMETRY"])
                gdf_necessarily.plot(ax=ax, color='blue', markersize=14, marker='^')
                gdf_necessarily = gdf_necessarily.set_geometry(gdf_necessarily["POINT"])
                gdf_necessarily.plot(ax=ax, color='blue', markersize=14, marker='^')

                piez = mpatches.Patch(color='black', fc='springgreen', label='Пьезометры')
                inj = mpatches.Patch(color='black', fc='azure', label='Нагнетательные')
                prod = mpatches.Patch(color='black', fc='lightsalmon', label='Добыващие(с исследованием)')
                necessarily = mpatches.Patch(color='black', fc='mistyrose',
                                             label='Скважины, исследуемые больше 1 раза в год')
                piez_point = Line2D([0], [0], marker='^', color='white', label='Скважины опорной сети',
                                    markerfacecolor='blue', markersize=14)
                prod_point = Line2D([0], [0], marker='.', color='white', label='Добывающий фонд',
                                    markerfacecolor='black', markersize=14)
                prod_point_exception = Line2D([0], [0], marker='.', color='white', label='Не охвачены исследованием',
                                              markerfacecolor='gray', markersize=14)
                proj_point = Line2D([0], [0], marker='.', color='white', label='Охваченный проектный фонд',
                                    markerfacecolor='crimson', markersize=14)
                proj_point_nonresearch = Line2D([0], [0], marker='.', color='gray', label='Неохваченный проектный фонд',
                                                markerfacecolor='crimson', markersize=14)
                line_1_year = Line2D([0], [0], color='gray', linestyle="-", lw=1, label='Исследования на текущий год')
                line_2_year = Line2D([0], [0], color='gray', linestyle=":", lw=1, label='На 2 год')
                line_3_year = Line2D([0], [0], color='gray', linestyle="-.", lw=1, label='На 3 год')

                if polygon is None:
                    plt.legend(
                        handles=[piez, inj, prod, necessarily, piez_point, prod_point, prod_point_exception, proj_point,
                                 proj_point_nonresearch, line_1_year, line_2_year, line_3_year])
                    try:
                        os.mkdir(f'{application_path}\\output\\regular_mesh\\out_contour')
                    except OSError:
                        pass
                    plt.savefig(
                        f'{application_path}\\output\\optimize_mesh\\out_contour\\{horizon.replace('/', '_')}, out contour, R = {int(mean_radius)}, k = {mult_coef}.png',
                        dpi=200)
                    plt.title(
                        f'Объект: {horizon.replace('/', '_')}, out contour, (R = {int(mean_radius)}, k = {mult_coef})')

                else:
                    plt.legend(
                        handles=[piez, inj, prod, necessarily, piez_point, prod_point, prod_point_exception, proj_point,
                                 proj_point_nonresearch, line_1_year, line_2_year, line_3_year])
                    try:
                        os.mkdir(f'{application_path}\\output\\regular_mesh\\{contour_name}')
                    except OSError:
                        pass
                    plt.savefig(
                        f'{application_path}\\output\\optimize_mesh\\{contour_name}\\{horizon.replace('/', '_')}, {contour_name}, R = {int(mean_radius)}, k = {mult_coef}.png',
                        dpi=200)
                    plt.title(
                        f'Объект: {horizon.replace('/', '_')}, контур: {contour_name}, (R = {int(mean_radius)}, k = {mult_coef})')
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
                (gpd.GeoSeries(gdf_prod[~(gdf_prod['wellName'].isin(list_exception))]["AREA"])
                 .boundary.plot(ax=ax, ls=type_lines[year], color=colors_prod[year]))

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

            # Trajectory of wells
            contour_prod_wells = contour_prod_wells.set_geometry(contour_prod_wells["GEOMETRY"])
            contour_prod_wells.plot(ax=ax, color="black", markersize=14, marker='.')
            gdf_measuring_all = gdf_measuring_all.set_geometry(df_result["GEOMETRY"])
            gdf_measuring_all.plot(ax=ax, color="blue", markersize=14, marker="^")

            # Black points is production, blue triangle is piezometric
            df_prod_nonexception = df_prod_nonexception.set_geometry(df_prod_nonexception["POINT"])
            df_prod_nonexception.plot(ax=ax, color="black", markersize=14)
            df_prod_nonexception = df_prod_nonexception.set_geometry(df_prod_nonexception["GEOMETRY"])
            df_prod_nonexception.plot(ax=ax, color="black", markersize=14)

            gdf_measuring_all = gdf_measuring_all.set_geometry(df_result["POINT"])
            gdf_measuring_all.plot(ax=ax, color="blue", markersize=14, marker="^")
            if len(contour_prod_exception):
                # Signature of excluded production wells
                for x, y, label in zip(df_prod_exception.coordinateX.values,
                                       df_prod_exception.coordinateY.values,
                                       df_prod_exception.wellName):
                    ax.annotate(label, xy=(x, y), xytext=(3, 3), textcoords="offset points", color="navy", fontsize=6)

                df_prod_exception = df_prod_exception.set_geometry(df_prod_exception["POINT"])
                df_prod_exception.plot(ax=ax, color="gray", markersize=14)
                df_prod_exception = df_prod_exception.set_geometry(df_prod_exception["GEOMETRY"])
                df_prod_exception.plot(ax=ax, color="gray", markersize=14)

            if not df_nonresearch_proj.empty:
                # Signature of unreseached project wells
                for x, y, label in zip(df_nonresearch_proj.coordinateX.values,
                                       df_nonresearch_proj.coordinateY.values,
                                       df_nonresearch_proj.wellName):
                    ax.annotate(label, xy=(x, y), xytext=(3, 3), textcoords="offset points", color="navy", fontsize=6)

                df_nonresearch_proj = df_nonresearch_proj.set_geometry(df_nonresearch_proj["GEOMETRY"])
                df_nonresearch_proj.plot(ax=ax, facecolor="crimson", markersize=14, edgecolor='gray')
                df_nonresearch_proj = df_nonresearch_proj.set_geometry(df_nonresearch_proj["POINT"])
                df_nonresearch_proj.plot(ax=ax, facecolor="crimson", markersize=18, edgecolor='gray')

            if not df_necessarily.empty:
                gdf_necessarily = gpd.GeoDataFrame(df_necessarily)
                # Signature of necessarily researched wells
                for x, y, label in zip(gdf_necessarily.coordinateX.values,
                                       gdf_necessarily.coordinateY.values,
                                       gdf_necessarily.wellName):
                    ax.annotate(label, xy=(x, y), xytext=(3, 3), textcoords="offset points", color="red", fontsize=6)

                gpd.GeoSeries(gdf_necessarily["AREA"]).plot(ax=ax, color='mistyrose')
                gpd.GeoSeries(gdf_necessarily["AREA"]).boundary.plot(ax=ax, color='indianred')
                gdf_necessarily = gdf_necessarily.set_geometry(gdf_necessarily["GEOMETRY"])
                gdf_necessarily.plot(ax=ax, color='blue', markersize=14, marker='^')
                gdf_necessarily = gdf_necessarily.set_geometry(gdf_necessarily["POINT"])
                gdf_necessarily.plot(ax=ax, color='blue', markersize=14, marker='^')

            if not df_research_project.empty:
                # Signature of reseached project wells
                for x, y, label in zip(df_research_project.coordinateX.values,
                                       df_research_project.coordinateY.values,
                                       df_research_project.wellName):
                    ax.annotate(label, xy=(x, y), xytext=(3, 3), textcoords="offset points", color="navy", fontsize=6)

                df_research_project = df_research_project.set_geometry(df_research_project["POINT"])
                df_research_project.plot(ax=ax, color="crimson", markersize=14)
                df_research_project = df_research_project.set_geometry(df_research_project["GEOMETRY"])
                df_research_project.plot(ax=ax, color="crimson", markersize=14)

            piez = mpatches.Patch(color='black', fc='springgreen', label='Пьезометры')
            inj = mpatches.Patch(color='black', fc='azure', label='Нагнетательные')
            prod = mpatches.Patch(color='black', fc='lightsalmon', label='Добыващие(с исследованием)')
            necessarily = mpatches.Patch(color='black', fc='mistyrose', label='Обязательные скважины')
            piez_point = Line2D([0], [0], marker='^', color='white', label='Скважины опорной сети',
                                markerfacecolor='blue', markersize=14)
            prod_point = Line2D([0], [0], marker='.', color='white', label='Добывающий фонд',
                                markerfacecolor='black', markersize=14)
            prod_point_exception = Line2D([0], [0], marker='.', color='white', label='Не охвачены исследованием',
                                          markerfacecolor='gray', markersize=14)
            proj_point = Line2D([0], [0], marker='.', color='white', label='Охваченный проектный фонд',
                                markerfacecolor='crimson', markersize=14)
            proj_point_nonresearch = Line2D([0], [0], marker='.', color='gray', label='Неохваченный проектный фонд',
                                            markerfacecolor='crimson', markersize=14)
            line_1_year = Line2D([0], [0], color='gray', linestyle="-", lw=1, label='Исследования на текущий год')
            line_2_year = Line2D([0], [0], color='gray', linestyle=":", lw=1, label='На 2 год')
            line_3_year = Line2D([0], [0], color='gray', linestyle="-.", lw=1, label='На 3 год')

            if polygon is None:
                plt.legend(
                    handles=[piez, inj, prod, necessarily, piez_point, prod_point, prod_point_exception, proj_point,
                             proj_point_nonresearch, line_1_year, line_2_year, line_3_year])
                try:
                    os.mkdir(f'{application_path}\\output\\regular_mesh\\out_contour')
                except OSError:
                    pass
                plt.savefig(
                    f'{application_path}\\output\\optimize_mesh\\out contour\\{horizon.replace('/', '_')}, out contour, R = {int(mean_radius)}, k = {mult_coef}.png',
                    dpi=200)
                plt.title(
                    f'Объект: {horizon.replace('/', '_')}, out contour, (R = {int(mean_radius)}, k = {mult_coef})')

            else:
                plt.legend(
                    handles=[piez, inj, prod, necessarily, piez_point, prod_point, prod_point_exception, proj_point,
                             proj_point_nonresearch, line_1_year, line_2_year, line_3_year])
                try:
                    os.mkdir(f'{application_path}\\output\\regular_mesh\\{contour_name}')
                except OSError:
                    pass
                plt.savefig(
                    f'{application_path}\\output\\optimize_mesh\\{contour_name}\\{horizon.replace('/', '_')}, {contour_name}, R = {int(mean_radius)}, k = {mult_coef}.png',
                    dpi=200)
                plt.title(
                    f'Объект: {horizon.replace('/', '_')}, контур: {contour_name}, (R = {int(mean_radius)}, k = {mult_coef})')

    pass


@logger.catch(level='DEBUG')
def mesh_visualization(df_input, dict_mesh, list_exception, percent, mean_oilrate_option):
    """
    Визуализация результатов, полученных в ходе сценария с построением ОС для каждого фонда по отдельности
    :param list_exception: список исключаемых скважин
    :param mean_oilrate_option: опция учета процента среднего дебита нефти по объекту
    :param df_input: DataFrame с исходными данными
    :param dict_mesh: словарь с результатами расчета
    :param percent: процент длины траектории скважины, при котором она попадает в контур
    :return: Сохраняется график, построенный по итерируемому объекту, в указанную директорию
    """
    logger.info("Clean pictures folder")
    application_path = get_path()
    # clean folder with previous calculation result pictures
    clean_pictures_folder(f'{application_path}\\output\\regular_mesh\\')
    logger.info('Begin plotting for 2 scenario')
    for key, value in tqdm(dict_mesh.items(), "Iterate by keys", position=0, leave=True, colour='white'):
        mult_coef = float(list(key.replace('=', ', ').split(', '))[-1])
        contour_name = list(key.replace(' = ', ', ').split(' k'))[0]
        df_result = value[0]
        polygon = value[1]
        list_objects = df_result[
            df_result['fond'] != 'ПРОЕКТ'].current_horizon.explode().unique()  # all objects of oilfield
        for obj in tqdm(list_objects, "Meshing for objects", position=0, leave=True, colour='white'):
            logger.info(f'Mapping object {obj}')
            gdf_research = gpd.GeoDataFrame(df_input[list(map(lambda x: len(set(x.replace(" ", "").split(",")) &
                                                                            set([obj])) > 0, df_input.workHorizon))])
            df_list_exception = gdf_research[gdf_research['wellName'].isin(list_exception)]
            gdf_list_exception = gpd.GeoDataFrame(df_list_exception)
            gdf_research = gdf_research[~gdf_research['wellName'].isin(df_result['wellName'].explode().unique())]
            # DataFrame исключенных скважин из листа "Исключения" исходного файла

            # выделение скважин на текущий объект расчета и отсеивание скважин, исключенных из ОС по проценту от фонда
            df_result_obj = df_result[
                (df_result['current_horizon'] == obj) & (
                    ~df_result['intersection'].map(str).str.contains('Исключена из ОС')) & (
                        df_result['num_of_research'] < 2)]
            df_necessarily = df_result[
                (df_result['current_horizon'] == obj) & (
                    ~df_result['intersection'].map(str).str.contains('Исключена из ОС')) & (
                        df_result['num_of_research'] > 1)]
            gdf_necessarily = gpd.GeoDataFrame(df_necessarily)
            gdf_result_obj = gpd.GeoDataFrame(df_result_obj)
            # выделение проектных скважин в отдельный GeoDataFrame и удаление их из gdf_result_obj
            gdf_research_proj = gdf_result_obj[gdf_result_obj['fond'] == 'ПРОЕКТ']
            gdf_proj = gdf_research[(gdf_research['fond'] == 'ПРОЕКТ') & (
                ~gdf_research['wellName'].isin(list(gdf_research_proj['wellName'].explode().unique())))]
            gdf_result_obj = gdf_result_obj[gdf_result_obj['fond'] != 'ПРОЕКТ']
            # выделение исследуемых скважин в контуре, если контура нет, то берутся все, кроме ОС
            if polygon is not None:
                gdf_research = gdf_research[gdf_research.wellName.isin(
                    list(check_intersection_area(polygon, gdf_research, percent, calc_option=True)))]
                gdf_proj = gdf_research[(gdf_research['fond'] == 'ПРОЕКТ') & (
                    ~gdf_research['wellName'].isin(list(gdf_research_proj['wellName'].explode().unique())))]
            else:
                logger.info('Mapping out contour')
                gdf_research = gdf_research[gdf_research['wellName'].isin(list(
                    set(gdf_result_obj[
                            (gdf_result_obj['current_horizon'] == obj) & (gdf_result_obj['fond'] != 'ПРОЕКТ')][
                            "intersection"].explode().unique())))]
            # скважины, исключенные из ОС
            df_result_exception = df_result[
                (df_result['current_horizon'] == obj) & (
                    df_result['intersection'].map(str).str.contains('Исключена из ОС'))]
            # проверка на охват исключенных скважин скважинами ОС
            df_result_exception = df_result_exception[df_result_exception['wellName'].isin(
                list(check_intersection_area(cascaded_union(gdf_result_obj['AREA'].explode().unique()),
                                             df_result_exception, percent, True)))]
            gdf_result_exception = gpd.GeoDataFrame(df_result_exception)

            gdf_research = gdf_research[
                gdf_research['wellName'].isin(list(gdf_result_obj['intersection'].explode().unique()))]
            # если в результирующем DataFrame кол-во строк больше 0, то отсеиваются скважины с дебитом больше среднего
            # по объекту и больше максимального, заданного пользователем
            if (gdf_result_obj.shape[0] != 0) and mean_oilrate_option:
                gdf_research = gdf_research.loc[gdf_research['oilRate'] <= gdf_result_obj['mean_oilrate'].iloc[0]]
            if gdf_result_obj.shape[0] != 0:
                gdf_research = gdf_research.loc[gdf_research['oilRate'] <= gdf_result_obj['limit_oilrate'].iloc[0]]
            gdf_piez = gdf_result_obj[df_result_obj['fond'] == 'ПЬЕЗ']
            gdf_inj = gdf_result_obj[df_result_obj['fond'] == 'НАГ']
            gdf_prod = gdf_result_obj[df_result_obj['fond'] == 'ДОБ']

            ax = gpd.GeoSeries(gdf_piez.AREA).plot(color="springgreen", figsize=[20, 20])
            gpd.GeoSeries(gdf_piez.AREA).boundary.plot(ax=ax, color="green")

            gpd.GeoSeries(gdf_inj.AREA).plot(ax=ax, color="azure")
            gpd.GeoSeries(gdf_inj.AREA).boundary.plot(ax=ax, color="lightseagreen")

            gpd.GeoSeries(gdf_prod.AREA).plot(ax=ax, color="lightsalmon")
            gpd.GeoSeries(gdf_prod.AREA).boundary.plot(ax=ax, color="orangered")

            # Boundary contour
            gpd.GeoSeries(polygon).boundary.plot(ax=ax, color='saddlebrown')

            # добавление названий скважин на картинках
            for x, y, label in zip(gdf_research.coordinateX.values,
                                   gdf_research.coordinateY.values,
                                   gdf_research.wellName):
                ax.annotate(label, xy=(x, y), xytext=(3, 3), textcoords="offset points", color="navy",
                            fontsize=6)

            for x, y, label in zip(gdf_result_obj.coordinateX.values,
                                   gdf_result_obj.coordinateY.values,
                                   gdf_result_obj.wellName):
                ax.annotate(label, xy=(x, y), xytext=(3, 3), textcoords="offset points", color="red", fontsize=6)

            # построение охваченных опорных скважин, исключенных из опорной сети
            if not gdf_result_exception.empty:
                for x, y, label in zip(gdf_result_exception.coordinateX.values,
                                       gdf_result_exception.coordinateY.values,
                                       gdf_result_exception.wellName):
                    ax.annotate(label, xy=(x, y), xytext=(3, 3), textcoords="offset points", color="red",
                                fontsize=6)

                gdf_result_exception = gdf_result_exception.set_geometry('POINT')
                gdf_result_exception.plot(ax=ax, color='gray', markersize=18, marker='^')
                gdf_result_exception = gdf_result_exception.set_geometry('GEOMETRY')
                gdf_result_exception.plot(ax=ax, color='gray', markersize=14, marker='^')

            # построение проектных скважин, которые не охвачены скважинами ОС
            if not gdf_proj.empty:
                # Signature of excluded production wells
                for x, y, label in zip(gdf_proj.coordinateX.values,
                                       gdf_proj.coordinateY.values,
                                       gdf_proj.wellName):
                    ax.annotate(label, xy=(x, y), xytext=(3, 3), textcoords="offset points", color="navy", fontsize=6)

                gdf_proj = gdf_proj.set_geometry(gdf_proj["POINT"])
                gdf_proj.plot(ax=ax, facecolor="crimson", markersize=18, edgecolor='gray')
                gdf_proj = gdf_proj.set_geometry(gdf_proj["GEOMETRY"])
                gdf_proj.plot(ax=ax, facecolor="crimson", markersize=14, edgecolor='gray')
            # построение обязательных скважин
            if not gdf_necessarily.empty:

                for x, y, label in zip(gdf_necessarily.coordinateX.values,
                                       gdf_necessarily.coordinateY.values,
                                       gdf_necessarily.wellName):
                    ax.annotate(label, xy=(x, y), xytext=(3, 3), textcoords="offset points", color="red", fontsize=6)
                gpd.GeoSeries(gdf_necessarily["AREA"]).plot(ax=ax, color='mistyrose')
                gpd.GeoSeries(gdf_necessarily["AREA"]).boundary.plot(ax=ax, color='indianred')
                gdf_necessarily = gdf_necessarily.set_geometry(gdf_necessarily["GEOMETRY"])
                gdf_necessarily.plot(ax=ax, color='blue', markersize=14, marker='^')
                gdf_necessarily = gdf_necessarily.set_geometry(gdf_necessarily["POINT"])
                gdf_necessarily.plot(ax=ax, color='blue', markersize=14, marker='^')
            # построение исключенных скважин
            if not gdf_list_exception.empty:
                for x, y, label in zip(gdf_list_exception.coordinateX.values,
                                       gdf_list_exception.coordinateY.values,
                                       gdf_list_exception.wellName):
                    ax.annotate(label, xy=(x, y), xytext=(3, 3), textcoords="offset points", color="navy", fontsize=6)

                gdf_list_exception = gdf_list_exception.set_geometry(gdf_list_exception["POINT"])
                gdf_list_exception.plot(ax=ax, color="maroon", markersize=18)
                gdf_list_exception = gdf_list_exception.set_geometry(gdf_list_exception["GEOMETRY"])
                gdf_list_exception.plot(ax=ax, color="maroon", markersize=14)

            if not gdf_research_proj.empty:
                # Signature of excluded production wells
                for x, y, label in zip(gdf_research_proj.coordinateX.values,
                                       gdf_research_proj.coordinateY.values,
                                       gdf_research_proj.wellName):
                    ax.annotate(label, xy=(x, y), xytext=(3, 3), textcoords="offset points", color="navy", fontsize=6)

                gdf_research_proj = gdf_research_proj.set_geometry(gdf_research_proj["POINT"])
                gdf_research_proj.plot(ax=ax, color="crimson", markersize=18)
                gdf_research_proj = gdf_research_proj.set_geometry(gdf_research_proj["GEOMETRY"])
                gdf_research_proj.plot(ax=ax, color="crimson", markersize=14)

            # построение траекторий скважин
            gdf_research = gdf_research.set_geometry('POINT')
            gdf_research.plot(ax=ax, color='black', markersize=14)
            gdf_research = gdf_research.set_geometry('GEOMETRY')
            gdf_research.plot(ax=ax, color='black', markersize=14)
            gdf_result_obj = gdf_result_obj.set_geometry('POINT')
            gdf_result_obj.plot(ax=ax, color="blue", markersize=14, marker='^')
            gdf_result_obj = gdf_result_obj.set_geometry('GEOMETRY')
            gdf_result_obj.plot(ax=ax, color='blue', markersize=14, marker='^')

            piez = mpatches.Patch(color='black', fc='springgreen', label='Пьезометры')
            inj = mpatches.Patch(color='black', fc='azure', label='Нагнетательные')
            prod = mpatches.Patch(color='black', fc='lightsalmon', label='Добыващие(с исследованием)')
            necessarily = mpatches.Patch(color='black', fc='mistyrose', label='Обязательные скважины')
            piez_point = Line2D([0], [0], marker='^', color='white', label='Скважины регулярной сети',
                                markerfacecolor='blue', markersize=14)
            prod_point = Line2D([0], [0], marker='.', color='white', label='Скважины, охваченные исследованиями',
                                markerfacecolor='black', markersize=14)
            piez_exception_point = Line2D([0], [0], marker='^', color='white',
                                          label='Скважины, исключенные из регулярной сети',
                                          markerfacecolor='gray', markersize=14)
            proj_point = Line2D([0], [0], marker='.', color='white', label='Охваченный проектный фонд',
                                markerfacecolor='crimson', markersize=14)
            proj_point_nonresearch = Line2D([0], [0], marker='.', color='gray', label='Неохваченный проектный фонд',
                                            markerfacecolor='crimson', markersize=14)
            exception_wells = Line2D([0], [0], marker='.', color='white', label='Исключенные скважины',
                                     markerfacecolor='maroon', markersize=14)

            if polygon is None:
                plt.legend(
                    handles=[piez, inj, prod, necessarily, piez_point, prod_point, piez_exception_point, proj_point,
                             proj_point_nonresearch, exception_wells])
                try:
                    os.mkdir(f'{application_path}\\output\\regular_mesh\\out_contour')
                except OSError:
                    pass
                plt.savefig(
                    f'{application_path}\\output\\regular_mesh\\out_contour\\{str(obj).replace('/', '_')}, out_contour, k = {mult_coef}.png',
                    dpi=200)
                plt.title(
                    f'Объект: {str(obj).replace('/', '_')}, out_contour, (k = {mult_coef})')

            else:
                plt.legend(
                    handles=[piez, inj, prod, necessarily, piez_point, prod_point, piez_exception_point, proj_point,
                             proj_point_nonresearch, exception_wells])
                try:
                    os.mkdir(f'{application_path}\\output\\regular_mesh\\{contour_name}')
                except OSError:
                    pass
                plt.savefig(
                    f'{application_path}\\output\\regular_mesh\\{contour_name}\\{str(obj).replace('/', '_')}, {contour_name}, k = {mult_coef}.png',
                    dpi=200)
                plt.title(
                    f'Объект: {str(obj).replace('/', '_')}, {contour_name}, (k = {mult_coef})')

    pass
