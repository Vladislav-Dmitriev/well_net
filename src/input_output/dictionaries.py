# Названия колонок для данных NGT.
# Переводит оригинальные названия в стандартизированные имена для работы с данными
dict_names_column = {
    '№ скважины': 'wellName',
    'Дата': 'nameDate',
    'Характер работы': 'workMarker',
    'Состояние': 'wellStatus',
    'Месторождение': 'oilfield',
    'Объекты работы': 'workHorizon',
    'Куст': 'wellCluster',
    'Координата X': 'coordinateXT1',
    'Координата Y': 'coordinateYT1',
    'Координата забоя Х (по траектории)': 'coordinateXT3',
    'Координата забоя Y (по траектории)': 'coordinateYT3',
    'Дебит нефти (ТР), т/сут': 'oilRate',
    'Дебит жидкости (ТР), м3/сут': 'fluidRate',
    'Приемистость (ТР), м3/сут': 'injectivity',
    'Обводненность (ТР), % (объём)': 'water_cut',
    'Способ эксплуатации': 'exploitation',
    'Дебит природного газа, тыс.м3/сут': 'gasRate',
    'Приемистость (по суточным), м3/сут': 'injectivity_day',
    'Дебит конденсата газа, т/сут': 'condRate',
    # 'Количество исследований за год': 'num_of_research'
}

# Названия колонок для данных GeoBD.
# Переводит столбцы GeoBD в стандартизированные имена
dict_geobd_columns = {
    'NSKV': 'wellName',
    'STATUS_DATE': 'nameDate',
    'FOND': 'workMarker',
    'SOST': 'wellStatus',
    'MEST': 'oilfield',
    'PLAST': 'workHorizon',
    'KUST': 'wellCluster',
    'X': 'coordinateX',
    'X3': 'coordinateX3',
    'Y': 'coordinateY',
    'Y3': 'coordinateY3',
    'DEBOIL': 'oilRate',
    'DEBLIQ': 'fluidRate',
    'DEBGAS': 'gasRate',
    'PRIEM': 'injectivity',
    'PRIEMGAS': 'injectivity_day',
    'VPROCOBV': 'water_cut',
    'SPOSOB': 'exploitation',
    'DEBCOND': 'condRate',
    'well type': 'well type',
    # 'RESEARCH': 'num_of_research'
}

# Названия колонок для проектных данных.
# Используется для получения данных из проектных файлов
dict_project_columns = {
    'NSKV': 'wellName',
    'X': 'coordinateX',
    'X3': 'coordinateX3',
    'Y': 'coordinateY',
    'Y3': 'coordinateY3',
    'PLAST': 'workHorizon',
    'well type': 'well type'
}

# Константы, используемые для фильтрации статусов скважин.
# Используются при обработке данных для отбора нужных типов скважин
dict_constant = {
    'PROD_STATUS': "раб|нак|ост",     # Статусы продуктивных скважин (например, рабочие, накопительные)
    'PROD_MARKER': "неф|газ|гк|конд", # Маркеры для продуктивных скважин (нефть, газ, конденсат)
    'PIEZ_STATUS': "пьез",            # Статус пьезометрических скважин
    'INJ_MARKER': "наг|пог",          # Маркеры для нагнетательных скважин
    'INJ_STATUS': "раб",              # Статус нагнетательных скважин
    'DELETE_STATUS': "лик|конс|перев|б/д|осв|безд|ост|проек"  # Статусы скважин, которые нужно исключить
}
