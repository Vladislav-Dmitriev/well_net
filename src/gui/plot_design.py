import json
import geopandas as gpd
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import shapely as spl
from loguru import logger
from matplotlib.lines import Line2D
from matplotlib.ticker import MultipleLocator


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
def plot_results(df_result, script):
    """
    Визуализация полученных результатов в зависимости от выбранного сценария расчета
    :param df_result: DataFrame с результатами расчета по текущему сценарию
    :param script: выбранный сценарий расчета
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
        'time_coef': 'Коэффициент для расчет времени исследования',
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
    # df_excluded = df_result[df_result['current_horizon'] == 0]
    df_result.loc[df_result['wellNet'].map(str).str.contains(
        'Охвачена исследованиями|Охвачена приоритетными'), 'status'] = 'covered'
    df_result.loc[df_result['wellNet'].str.lower().str.contains('исключена|не охвачена'), 'status'] = 'excluded'
    df_result.loc[df_result['fond'] == 'ПРОЕКТ', 'status'] = 'project'
    df_result.loc[df_result['wellNet'] == 'Выбрана в опорную сеть', 'status'] = 'included'

    fig, ax = plt.subplots(figsize=(20, 20))
    fig.set_size_inches(7, 7)
    # построение контура
    if df_result.iloc[0]['polygon'] != 0:
        (gpd.GeoSeries(spl.geometry.shape(json.loads(df_result.iloc[0]['polygon']))).
         boundary.plot(ax=ax, color='saddlebrown'))
    # построение зон исследования скважин опорной сети
    for index, row in df_result[df_result['status'] == 'included'].iterrows():
        area_color = get_color_area(row['fond'])
        line_type, line_color = get_linetype_color(row['fond'], row['year_of_survey'])
        gpd.GeoSeries(row['AREA']).plot(ax=ax, facecolor=area_color, alpha=0.7)
        gpd.GeoSeries(row['AREA']).boundary.plot(ax=ax, ls=line_type, color=line_color)

    for index, row in df_result.drop_duplicates(subset='wellName').iterrows():
        # получение цвета геометрии в зависимости от статуса скважины и маркера точки T1 для нее
        geometry_color, marker, font_color = get_geometry_color(row['status'])
        gpd.GeoSeries(row['GEOMETRY']).plot(ax=ax, color=geometry_color, marker='.')
        ax.scatter(row['coordinateX'], row['coordinateY'], color=geometry_color, marker=marker)
        ax.annotate(row['wellName'], xy=(row['coordinateX'], row['coordinateY']), xytext=(3, 3),
                    textcoords="offset points", fontsize=6, color=font_color)

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

    if script == 'Оптимальная сетка':
        line_1_year = Line2D([0], [0], color='gray', linestyle="-", lw=1, label='Исследования на текущий год')
        line_2_year = Line2D([0], [0], color='gray', linestyle=":", lw=1, label='На 2 год')
        line_3_year = Line2D([0], [0], color='gray', linestyle="-.", lw=1, label='На 3 год')
        handles += [line_1_year, line_2_year, line_3_year]

    # Сохранение картинок в формате .png
    if df_result.iloc[0]['polygon'] is None:
        ax.legend(handles=handles, loc='upper right')
    else:
        handles += [contour_boundary]
        ax.legend(handles=handles, loc='upper right')
    # ax.set_position([0.1, 0.1, 0.85, 0.85])
    # ax.set_aspect('auto')
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    # ax.spines['left'].set_visible(False)
    # ax.spines['bottom'].set_visible(False)
    ax.spines['left'].set_position(('outward', 0))  # Левую ось двигаем к левому краю
    ax.spines['bottom'].set_position(('outward', 0))  # Нижнюю ось двигаем к нижнему краю
    ax.xaxis.set_ticks_position('bottom')
    ax.yaxis.set_ticks_position('left')

    plt.subplots_adjust(left=0, right=1, top=1, bottom=0)
    ax.tick_params(axis='both', direction='in')
    plt.tight_layout()
    return fig, ax
