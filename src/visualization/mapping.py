import os
import shutil
import geopandas as gpd
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import pandas as pd
from loguru import logger
from matplotlib.lines import Line2D
from tqdm import tqdm

from src.calculation.geometry import check_intersection_area
from src.calculation.auxiliary_functions import get_path


@logger.catch(level='DEBUG')
def clean_pictures_folder(path, pictures_folder):
    """
    Функция очищает папку с рисунками предыдущего расчета
    :param pictures_folder:
    :param path: путь к папке с рисунками
    :return: не возвращает объектов, удаляет содержимое папки
    """
    path = os.path.join(path, 'output', pictures_folder)
    if os.path.isdir(path):
        logger.info("Clean pictures folder")
        # Перебираем все элементы в директории
        for item in os.listdir(path):
            item_path = os.path.join(path, item)
            # Если элемент является папкой, удаляем его
            if os.path.isdir(item_path):
                shutil.rmtree(item_path)
    else:
        os.mkdir(os.path.join(path))

    pass


def get_color_area(fond):
    """
    Определение цвета зоны, охваченной исследованием
    :param fond: Фонд, к которому относится скважина.
    :return: Строка с названием цвета, в который нужно покрасить зону охвата скважины ОС
    """
    dict_area_colors = {'ПЬЕЗ': "springgreen", 'НАГ': "azure", 'ДОБ': "lightsalmon"}

    return dict_area_colors[fond]


def get_linetype_color(fond, year):
    """
    Выбор стиля и цвета линии обводки в зависимости от фонда и года исследования скважины
    :param fond: фонд скважины
    :param year: год исследования
    :return: тип и цвет линии в зависимости от года исследования и фонда скважины
    """
    dict_linetype_color = {'ПЬЕЗ': {0: ["-", "darkgreen"], 1: [":", "green"], 2: ["-.", "limegreen"]},
                           'НАГ': {0: ["-", "lightseagreen"], 1: [":", "turquoise"], 2: ["-.", "lightskyblue"]},
                           'ДОБ': {0: ["-", "orangered"], 1: [":", "tomato"], 2: ["-.", "coral"]}}
    line_type = dict_linetype_color[fond][year][0]
    line_color = dict_linetype_color[fond][year][1]

    return line_type, line_color


def get_geometry_color(status):
    """
    Получение цвета геометрии(токи или линии), маркера и подписи скважины на картинке статуса по опорной сети
    :param status: статус скважины по опорной сети
    :return: цвет геометрии, маркер и цвет шрифта для подписи скважины
    """
    dict_status = {'included': ['blue', '^', 'red'], 'excluded': ['gray', '.', 'blue'],
                   'covered': ['black', '.', 'blue'], 'project': ['chocolate', '.', 'blue']}
    geometry_color = dict_status[status][0]
    marker = dict_status[status][1]
    font_color = dict_status[status][2]

    return geometry_color, marker, font_color


@logger.catch(level='DEBUG')
def plot_results(dict_result, df_exceptions, dict_parameters):
    """
    Визуализация полученных результатов в зависимости от выбранного сценария расчета
    :param dict_result: словарь с результатами расчета
    :param df_exceptions: DataFrame c исключенными скважинами во время подготовки к расчету
    :param dict_parameters: словарь с параметрами расчета
    :return: Сохранение картинок с опорной сеткой для разных объектов и разных радиусов исследования
    """
    # path to root folder
    application_path = get_path()
    # create or clean folder with pictures
    if dict_parameters['calculation_scenario'] == 'optimize':
        pictures_folder = 'Оптимальная сетка'
    else:
        pictures_folder = 'Регулярная сетка'
    clean_pictures_folder(application_path, pictures_folder)

    for key, value in tqdm(dict_result.items(), "Plot result pictures", position=0, leave=True,
                           colour='white', ncols=80):
        contour_name = key.split(' k=')[0]  # имя контура
        mult_coef = float(key.split(' k=')[1])  # коэффициент кратного увеличения радиуса исследования
        logger.info(f'Current calculation contour {contour_name}, coefficient {mult_coef}')
        df_result = value[0]
        mean_radius = df_result[df_result['wellNet'] == 'Выбрана в опорную сеть'].iloc[0]['mean_radius']
        contour = value[1]
        if contour is None:
            df_excluded = df_exceptions.copy()
        else:
            df_excluded = df_exceptions[df_exceptions['wellName'].isin(
                set(check_intersection_area(contour, df_exceptions, dict_parameters['percent'],
                                            dict_parameters['calc_option'])))]
        df_excluded['status'] = 'excluded'
        # список объектов
        list_key_objects = list(df_result['current_horizon'].explode().unique())
        # добавление маркеров, упрощающих различие по статусам скважин по опорной сети
        df_result['status'] = ''
        df_result.loc[df_result['wellNet'].map(str).str.contains(
            'Охвачена исследованиями|Охвачена приоритетными'), 'status'] = 'covered'
        df_result.loc[df_result['wellNet'].str.lower().str.contains('исключ|не охвачена'), 'status'] = 'excluded'
        df_result.loc[df_result['fond'] == 'ПРОЕКТ', 'status'] = 'project'
        df_result.loc[df_result['wellNet'] == 'Выбрана в опорную сеть', 'status'] = 'included'

        for horizon in tqdm(list_key_objects, "Mapping for objects", position=0, leave=True, colour='white'):
            # выделение скважин на объект итерации
            logger.info(f'Plot picture for object {horizon}')
            df_horizon = pd.concat([df_result[df_result['current_horizon'] == horizon], df_excluded],
                                   axis=0, sort=False).reset_index(drop=True)
            fig, ax = plt.subplots(figsize=(20, 20))
            # построение контура
            gpd.GeoSeries(contour).boundary.plot(ax=ax, color='saddlebrown')
            # построение зон исследования скважин опорной сети
            for index, row in df_horizon[df_horizon['status'] == 'included'].iterrows():
                area_color = get_color_area(row['fond'])
                line_type, line_color = get_linetype_color(row['fond'], row['year_of_survey'])
                gpd.GeoSeries(row['AREA']).plot(ax=ax, facecolor=area_color, alpha=0.7)
                gpd.GeoSeries(row['AREA']).boundary.plot(ax=ax, ls=line_type, color=line_color)


            for index, row in df_horizon.iterrows():
                # получение цвета геометрии в зависимости от статуса скважины и маркера точки T1 для нее
                geometry_color, marker, font_color = get_geometry_color(row['status'])
                gpd.GeoSeries(row['GEOMETRY']).plot(ax=ax, color=geometry_color, marker='.')
                ax.scatter(row['coordinateX'], row['coordinateY'], color=geometry_color, marker=marker)
                ax.annotate(row['wellName'], xy=(row['coordinateX'], row['coordinateY']), xytext=(3, 3),
                            textcoords="offset points", fontsize=6, color=font_color)

            # создание папки для сохранения картинок, если ее нет
            try:
                os.mkdir(f'{application_path}\\output\\{pictures_folder}\\{contour_name}')
            except OSError:
                pass

            piez = mpatches.Patch(color='black', fc='springgreen', label='Пьезометры')
            inj = mpatches.Patch(color='black', fc='azure', label='Нагнетательные')
            prod = mpatches.Patch(color='black', fc='lightsalmon', label='Добыващие(с исследованием)')
            wellnet_point = Line2D([0], [0], marker='^', color='white', label='Включены в программу ГДИС',
                                markerfacecolor='blue', markersize=14)
            research_wells = Line2D([0], [0], marker='.', color='white', label='Охваченные исследованиями',
                                markerfacecolor='black', markersize=14)
            proj_wells = Line2D([0], [0], marker='.', color='white', label='Проектный фонд',
                                markerfacecolor='chocolate', markersize=14)
            exception_wells = Line2D([0], [0], marker='.', color='white', label='Исключенные',
                                     markerfacecolor='gray', markersize=14)
            contour_boundary = Line2D([0], [0], marker='_', color='saddlebrown', label='Граница контура',
                                      markerfacecolor='saddlebrown', markersize=14)
            handles = [piez, inj, prod, wellnet_point, research_wells, proj_wells, exception_wells]

            if dict_parameters['calculation_scenario'] == 'optimize':
                line_1_year = Line2D([0], [0], color='gray', linestyle="-", lw=1, label='Исследования на текущий год')
                line_2_year = Line2D([0], [0], color='gray', linestyle=":", lw=1, label='На 2 год')
                line_3_year = Line2D([0], [0], color='gray', linestyle="-.", lw=1, label='На 3 год')
                handles += [line_1_year, line_2_year, line_3_year]

            # Сохранение картинок в формате .png
            if contour is None:
                plt.legend(handles=handles)
                plt.savefig(os.path.join(application_path, 'output', pictures_folder, contour_name,
                                         f'Объект {horizon.replace('/', '_')}, R = {int(mean_radius)},'
                                         f' k = {mult_coef}.png'), dpi=200)
                plt.title(f'Объект: {horizon.replace('/', '_')}, без контуров, (R = {int(mean_radius)},'
                          f' k = {mult_coef})')

            else:
                handles += [contour_boundary]
                plt.legend(handles=handles)
                plt.savefig(os.path.join(application_path, 'output', pictures_folder, contour_name,
                                         f'Объект {horizon.replace('/', '_')}, R = {int(mean_radius)},'
                                         f' k = {mult_coef}.png'), dpi=200)
                plt.title(f'Объект: {horizon.replace('/', '_')}, контур: {contour_name}, R = {int(mean_radius)},'
                          f' k = {mult_coef}')

    pass
