# input NGT data column names
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
    'Дебит конденсата газа, т/сут': 'condRate'
}

# input GeoBD data column names
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
    'well type': 'well type'
}

# CONSTANT
dict_constant = {
    'PROD_STATUS': "раб|нак|ост",
    'PROD_MARKER': "неф|газ|водозаб|вдз|гк|конд",
    'PIEZ_STATUS': "пьез",
    'INJ_MARKER': "наг|пог",
    'INJ_STATUS': "раб",
    'DELETE_STATUS': "лик|конс|перев|б/д|осв"}
