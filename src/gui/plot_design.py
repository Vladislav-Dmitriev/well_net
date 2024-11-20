import json
import geopandas as gpd
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import shapely as spl
from loguru import logger
from matplotlib.lines import Line2D
from matplotlib_scalebar.scalebar import ScaleBar
from matplotlib.widgets import CheckButtons


@logger.catch(level='DEBUG')
def get_color_area(fond):
    """
    Определение цвета зоны, охваченной исследованием
    :param fond: Фонд, к которому относится скважина.
    :return: Строка с названием цвета, в который нужно покрасить зону охвата скважины ОС
    """
    dict_area_colors = {'ПЬЕЗ': "springgreen", 'НАГ': "azure", 'ДОБ': "lightsalmon"}

    return dict_area_colors[fond]


@logger.catch(level='DEBUG')
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


@logger.catch(level='DEBUG')
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
def plot_results(df_result, script):
    """
    Визуализация полученных результатов в зависимости от выбранного сценария расчета
    :param df_result: DataFrame с результатами расчета по текущему сценарию
    :param script: сценарий расчета
    :return: Сохранение картинок с опорной сеткой для разных объектов и разных радиусов исследования
    """
    dict_rename = {
        'wellName': '№ скважины',
        'nameDate': 'Дата',
        'workMarker': 'Характер работы',
        'wellStatus': 'Состояние',
        'oilfield': 'Месторождение',
        'workHorizon': 'Объекты работы',
        'wellCluster': 'Куст',
        'coordinateX': 'Координата X',
        'coordinateX3': 'Координата забоя Х (по траектории)',
        'coordinateY': 'Координата Y',
        'coordinateY3': 'Координата забоя Y (по траектории)',
        'oilRate': 'Дебит нефти (ТР), т/сут',
        'fluidRate': 'Дебит жидкости (ТР), м3/сут',
        'gasRate': 'Дебит природного газа, тыс.м3/сут',
        'injectivity': 'Приемистость (ТР), м3/сут',
        'injectivity_day': 'Приемистость (по суточным), м3/сут',
        'water_cut': 'Обводненность (ТР), % (объём)',
        'exploitation': 'Способ эксплуатации',
        'condRate': 'Дебит конденсата газа, т/сут',
        'well type': 'Тип скважины',
        'fond': 'Фонд скважины',
        'GEOMETRY': 'GEOMETRY',
        'num_of_research': 'Количество исследований в год',
        'AREA': 'AREA',
        'intersection': 'Пересечения со скважинами',
        'number': 'Кол-во пересечений',
        'mean_radius': 'Средний радиус по объекту, м',
        'time_coef': 'Коэффициент для расчета времени исследования',
        'k': 'Проницаемость, мД',
        'gas_visc': 'Вязкость газа в пластовых условиях, сПз',
        'pressure': 'Начальное пластовое давление (карты изобар), атм',
        'default_count': 'Объектов по умолчанию',
        'obj_count': 'Объектов всего',
        'percent_of_default': 'Процент объектов со свойствами по умолчанию',
        'current_horizon': 'Объект расчета',
        'research_time': 'Время исследования, сут',
        'oil_loss': 'Потери нефти, т',
        'gas_loss': 'Потери газа, тыс. м3',
        'injection_loss': 'Потери закачки, м3',
        'coverage_percentage': 'Процент охвата площади объекта',
        'percent_piez_wells': 'Доля пьезометров в опорной сети',
        'percent_inj_wells': 'Доля нагнетательных в опорной сети',
        'percent_prod_wells': 'Доля добывающих в опорной сети',
        'percent_gas_wells': 'Доля газовых добывающих скважин в опорной сети',
        'year_of_survey': 'Год исследования',
        'mean_oilrate': 'Средний дебит нефти по объекту, т/сут',
        'wellNet': 'Статус по опорной сети',
        'polygon': 'polygon'
    }

    dict_rename = {v: k for k, v in dict_rename.items()}
    df_result.columns = dict_rename.values()
    df_result['AREA'] = df_result['AREA'].apply(lambda x: spl.geometry.shape(json.loads(x)) if x != 0 else x)
    df_result['GEOMETRY'] = df_result['GEOMETRY'].apply(lambda x: spl.geometry.shape(json.loads(x)))
    # добавление маркеров, упрощающих различие по статусам скважин по опорной сети
    df_result['status'] = ''

    df_result.loc[df_result['wellNet'].map(str).str.contains(
        'Охвачена исследованиями|Охвачена приоритетными'), 'status'] = 'covered'
    df_result.loc[
        df_result['wellNet'].str.lower().str.contains('исключена|не охвачена|в списке искл'), 'status'] = 'excluded'
    df_result.loc[df_result['fond'] == 'ПРОЕКТ', 'status'] = 'project'
    df_result.loc[df_result['wellNet'] == 'Выбрана в опорную сеть', 'status'] = 'included'

    # Подготовка данных для отображения
    fig, ax = plt.subplots(figsize=(7, 7))
    dict_shapes = {
        "excluded_points": [],
        "excluded_geometry": [],
        "excluded_annotation": [],
        "areas": [],
        "areas_contour": []
    }

    # Построение контура
    if df_result.iloc[0]['polygon'] != 0:
        (gpd.GeoSeries(spl.geometry.shape(json.loads(df_result.iloc[0]['polygon'])))
         .boundary.plot(ax=ax, color='saddlebrown'))

    # Построение зон исследования для "included" объектов
    for _, row in df_result[df_result['status'] == 'included'].iterrows():
        area_color = get_color_area(row['fond'])
        line_type, line_color = get_linetype_color(row['fond'], row['year_of_survey'])
        polygon_area = row['AREA']
        x, y = polygon_area.exterior.xy
        polygon = ax.fill(x, y, facecolor=area_color, alpha=0.7)
        dict_shapes['areas'].append(polygon)
        line, = ax.plot(*polygon_area.boundary.xy, ls=line_type, color=line_color)
        dict_shapes['areas_contour'].append(line)

    # Отображение скважин и геометрии
    for _, row in df_result.drop_duplicates(subset='wellName').iterrows():
        geometry_color, marker, font_color = get_geometry_color(row['status'])
        geometry = gpd.GeoSeries(row['GEOMETRY'])
        line, = ax.plot(*geometry.loc[0].xy, color=geometry_color)
        point = ax.scatter(row['coordinateX'], row['coordinateY'], color=geometry_color, marker=marker, label='All')
        annotate = ax.annotate(row['wellName'], xy=(row['coordinateX'], row['coordinateY']), xytext=(3, 3),
                               textcoords="offset points", fontsize=6, color=font_color)
        if row['status'] == 'excluded':
            dict_shapes['excluded_points'].append(point)
            dict_shapes['excluded_geometry'].append(line)
            dict_shapes['excluded_annotation'].append(annotate)

    # Легенда для различных типов объектов
    piez = mpatches.Patch(color='black', fc='springgreen', label='Пьезометры')
    inj = mpatches.Patch(color='black', fc='azure', label='Нагнетательные')
    prod = mpatches.Patch(color='black', fc='lightsalmon', label='Добыващие(с исследованием)')
    wellnet_point = Line2D([0], [0], marker='^', color='black', label='Включены в программу ГДИС',
                           markerfacecolor='blue', markersize=14, linestyle='None')
    research_wells = Line2D([0], [0], marker='.', color='black', label='Охваченные исследованиями',
                            markerfacecolor='black', markersize=14, linestyle='None')
    proj_wells = Line2D([0], [0], marker='.', color='black', label='Проектный фонд',
                        markerfacecolor='chocolate', markersize=14, linestyle='None')
    exception_wells = Line2D([0], [0], marker='.', color='black', label='Исключенные',
                             markerfacecolor='gray', markersize=14, linestyle='None')
    contour_boundary = Line2D([0], [0], marker='_', color='black', label='Граница контура',
                              markerfacecolor='saddlebrown', markersize=14, linestyle='None')
    handles = [piez, inj, prod, wellnet_point, research_wells, proj_wells, exception_wells]

    # Условная легенда для сценария "Оптимальная сетка"
    if script == 'Оптимальная сетка':
        line_1_year = Line2D([0], [0], color='black', linestyle="-", lw=1, label='Исследования на текущий год')
        line_2_year = Line2D([0], [0], color='black', linestyle=":", lw=1, label='На 2 год')
        line_3_year = Line2D([0], [0], color='black', linestyle="-.", lw=1, label='На 3 год')
        handles += [line_1_year, line_2_year, line_3_year]

    # Добавление контура к легенде
    if df_result.iloc[0]['polygon'] != 0:
        handles += [contour_boundary]

    # добавление новых осей для фиксации легенды
    legend_axes = fig.add_axes([0.78, 0.65, 0.2, 0.35], zorder=5)
    legend_axes.set_axis_off()
    legend = legend_axes.legend(handles=handles, fancybox=True, framealpha=0.5)

    # Формат координат и отключение осей
    ax.format_coord = lambda x, y: f'x={x:.2f}, y={y:.2f}'
    ax.set_aspect('equal')
    ax.set_axis_off()

    # Добавление масштабной линейки
    scalebar = ScaleBar(1, location='lower left', box_alpha=0, dimension='si-length', pad=0.5)
    ax.add_artist(scalebar)

    # Добавление панели с CheckButtons для кастомного управления элементами графика
    checkbox_ax = fig.add_axes([0.01, 0.85, 0.15, 0.15], zorder=5)  # фиксированная позиция для панели
    checkbox_ax.set_axis_off()
    checkbox_labels = ['Легенда', 'Исключенные скважины', 'Зоны исследования']
    checkbox_activated = [True, True, True]
    check = CheckButtons(checkbox_ax, checkbox_labels, checkbox_activated)

    def update(val):
        # Обновляем видимость элементов
        if check.get_status()[0]:  # Легенда
            # Создание легенды
            legend.set_visible(True)
        else:
            legend.set_visible(False)

        if check.get_status()[1]:  # Исключенные скважины
            for point in dict_shapes['excluded_points']:
                point.set_visible(True)
            for line in dict_shapes['excluded_geometry']:
                line.set_visible(True)
            for annotate in dict_shapes['excluded_annotation']:
                annotate.set_visible(True)
        else:
            for point in dict_shapes['excluded_points']:
                point.set_visible(False)
            for line in dict_shapes['excluded_geometry']:
                line.set_visible(False)
            for annotate in dict_shapes['excluded_annotation']:
                annotate.set_visible(False)

        if check.get_status()[2]:  # Зоны исследования
            for area in dict_shapes['areas']:
                # Для каждой области нужно отдельно установить видимость каждого элемента
                if isinstance(area, list):  # Если это список, проходим по всем его элементам
                    for patch in area:
                        patch.set_visible(True)
                else:  # Если это одиночный объект, просто меняем его видимость
                    area.set_visible(True)

            for contour in dict_shapes['areas_contour']:
                # Процесс с контурами аналогичен
                contour.set_visible(True)
        else:
            for area in dict_shapes['areas']:
                if isinstance(area, list):
                    for patch in area:
                        patch.set_visible(False)
                else:
                    area.set_visible(False)

            for contour in dict_shapes['areas_contour']:
                contour.set_visible(False)

        fig.canvas.draw_idle()

    check.on_clicked(update)

    return fig, ax, check
