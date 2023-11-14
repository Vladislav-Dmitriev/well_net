import pandas as pd
import xlwings as xw
from tqdm import tqdm

from functions import unpack_status


def write_to_excel(dict_result, **dict_constant):
    """
    Для записи результата расчетов в Excel подается словарь
    Для каждого ключа создается отдельный лист в документе
    :param dict_constant: словарь со статусами скважин
    :param dict_result: словарь, по ключам которого содержатся DataFrame для каждого контура
    :return: функция сохраняет файл в указанную директорию
    """
    # result dict rename columns in russian
    dict_rename_columns = {
        'wellName': '№ скважины',
        'nameDate': 'Дата',
        'workMarker': 'Характер работы',
        'wellStatus': 'Состояние',
        'oilfield': 'Месторождение',
        'workHorizon': 'Объекты работы',
        'wellCluster': 'Куст',
        'oilRate': 'Дебит нефти (ТР), т/сут',
        'injectivity': 'Приемистость (ТР), м3/сут',
        'water_cut': 'Обводненность (ТР), % (объём)',
        'wellType': 'Тип скважины',
        'coordinateX': 'Координата X',
        'coordinateX3': 'Координата забоя Х (по траектории)',
        'coordinateY': 'Координата Y',
        'coordinateY3': 'Координата забоя Y (по траектории)',
        'intersection': 'Пересечения со скважинами',
        'number': 'Кол-во пересечений',
        'mean_radius': 'Средний радиус по объекту, м',
        'time_coef': 'Коэффициент для расчет времени исследования',
        'default_count': 'Объектов по умолчанию',
        'obj_count': 'Объектов всего',
        'percent_of_default': 'Процент объектов по умолчанию',
        'current_horizon': 'Объект расчета',
        'research_time': 'Время исследования, сут',
        'oil_loss': 'Потери нефти, т',
        'injection_loss': 'Потери закачки, м3',
        'year_of_survey': 'Год исследования'
    }

    app1 = xw.App(visible=False)
    new_wb = xw.Book()

    for key, value in tqdm(dict_result.items(), "Write to excel file"):
        name = str(key).replace("/", " ")

        if f"{name}" in new_wb.sheets:
            xw.Sheet[f"{name}"].delete()

        if value[0].empty:
            continue
        else:
            new_wb.sheets.add(f"{name}")

        sht = new_wb.sheets(f"{name}")
        df = value[0].copy()
        df["intersection"] = list(map(lambda x: " ".join(str(y) for y in x), df["intersection"]))
        df.drop(columns=['distance', 'mean_dist', 'POINT', 'POINT3', 'GEOMETRY', 'AREA'], axis=1, inplace=True)
        df.columns = dict_rename_columns.values()
        sht.range('A1').options().value = df
    df_report = get_report(dict_result, **dict_constant)
    if "report" in new_wb.sheets:
        xw.Sheet["report"].delete()
    new_wb.sheets.add("report")
    sht = new_wb.sheets("report")
    sht.range('A1').options().value = df_report
    new_wb.save("output/out_file_geometry.xlsx")
    # End print
    app1.kill()
    pass


def get_report(dict_result, **dict_constant):
    """
    Функция для создания краткого отчета по всем контурам с разными коэффициентами для радиусов охвата
    :param dict_result: словарь с результатами расчетов по всем объектам
    :param dict_constant: словарь со статусами скважин
    :return: возвращает DataFrame с отчетом по каждому контуру с определенным коэффициентом домножения радиуса
    """
    dict_names_report = {'contour_k': 'Сценарий',
                         'obj_count': 'Кол-во объектов',
                         'mean_rad': 'Средний радиус',
                         'mean_time': 'Среднее время исследования',
                         'piez_count': 'Кол-во пьезометров',
                         'inj_count': 'Кол-во нагн',
                         'prod_count': 'Кол-во доб',
                         'well_quantity0': 'Кол-во исслед. скв. 1 год',
                         'well_quantity1': 'Кол-во исслед. скв. 2 год',
                         'well_quantity2': 'Кол-во исслед. скв. 3 год',
                         'research_wells0': 'Охваченные исследованиями 1 год',
                         'research_wells1': 'Охваченные исследованиями 2 год',
                         'research_wells2': 'Охваченные исследованиями 3 год',
                         'oil_loss0': 'Потери нефти 1 год, т',
                         'oil_loss1': 'Потери нефти 2 год, т',
                         'oil_loss2': 'Потери нефти 3 год, т',
                         'injection_loss0': 'Потери закачки 1 год, м3',
                         'injection_loss1': 'Потери закачки 2 год, м3',
                         'injection_loss2': 'Потери закачки 3 год, м3',
                         'percent_of_default': 'Процент объектов по умолчанию'}

    PROD_STATUS, PROD_MARKER, PIEZ_STATUS, INJ_MARKER, INJ_STATUS = unpack_status(dict_constant)
    dict_report = {}

    for key, value in tqdm(dict_result.items(), "Preparing report", position=0, leave=True, ncols=80):
        df = value[0]
        if df.empty:
            continue
        dict_report['contour_k'] = dict_report.get('contour_k', []) + [key]
        dict_report['obj_count'] = dict_report.get('obj_count', []) + [len(set(df['workHorizon'].explode().unique()))]
        dict_report['mean_rad'] = dict_report.get('mean_rad', []) + [df['mean_radius'].mean()]
        dict_report['mean_time'] = dict_report.get('mean_time', []) + [df['research_time'].mean()]
        dict_report['piez_count'] = dict_report.get('piez_count', []) + [len(df.loc[df.wellStatus == PIEZ_STATUS])]
        dict_report['inj_count'] = dict_report.get('inj_count', []) + [len(
            df.loc[(df.workMarker == INJ_MARKER) & (df.wellStatus.isin(INJ_STATUS))])]
        dict_report['prod_count'] = dict_report.get('prod_count', []) + [len(
            df.loc[(df.workMarker == PROD_MARKER) & (df.wellStatus.isin(PROD_STATUS))])]

        dict_report['well_quantity0'] = dict_report.get('well_quantity0', []) + [df[df['year_of_survey'] == 0].shape[0]]
        dict_report['well_quantity1'] = (dict_report.get('well_quantity1', []) +
                                         [df[df['year_of_survey'] == 1].shape[0]])
        dict_report['well_quantity2'] = (dict_report.get('well_quantity2', []) +
                                         [df[df['year_of_survey'] == 2].shape[0]])

        dict_report['research_wells0'] = (dict_report.get('research_wells0', []) +
                                          [len(set(df[df['year_of_survey'] == 0].intersection.explode().unique()))])
        dict_report['research_wells1'] = dict_report.get('research_wells1', []) + [
            len(set(df[df['year_of_survey'] == 1].intersection.explode().unique()))]
        dict_report['research_wells2'] = dict_report.get('research_wells2', []) + [
            len(set(df[df['year_of_survey'] == 2].intersection.explode().unique()))]

        dict_report['oil_loss0'] = dict_report.get('oil_loss0', []) + [df[df['year_of_survey'] == 0].oil_loss.sum()]
        dict_report['oil_loss1'] = dict_report.get('oil_loss1', []) + [df[df['year_of_survey'] == 1].oil_loss.sum()]
        dict_report['oil_loss2'] = dict_report.get('oil_loss2', []) + [df[df['year_of_survey'] == 2].oil_loss.sum()]

        dict_report['injection_loss0'] = (dict_report.get('injection_loss0', []) +
                                          [df[df['year_of_survey'] == 0].injection_loss.sum()])
        dict_report['injection_loss1'] = (dict_report.get('injection_loss1', []) +
                                          [df[df['year_of_survey'] == 1].injection_loss.sum()])
        dict_report['injection_loss2'] = dict_report.get('injection_loss2', []) + [
            df[df['year_of_survey'] == 2].injection_loss.sum()]
        dict_report['percent_of_default'] = (dict_report.get('percent_of_default', []) +
                                             [100 * df.default_count.sum() / df.obj_count.sum()])

    df_report = pd.DataFrame.from_dict(dict_report, orient='columns')
    df_report.rename(columns=dict_names_report, inplace=True)

    return df_report
