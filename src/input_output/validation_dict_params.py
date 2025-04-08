from pydantic import field_validator, BaseModel, ValidationError, Field
from typing import Union
from loguru import logger
import pandas as pd
import os


class ValidateToBD(BaseModel):

    data_file: str = Field(..., description='data_file')
    calculation_scenario: str = Field(..., description='calculation_scenario')
    gdis_option: Union[str, str] = Field(..., description='gdis_option')
    calc_option: str = Field(..., description='calc_option')
    percent: float = Field(..., description='percent')
    horizon_count: Union[int, str] = Field(..., description='horizon_count')
    mult_coef: list = Field(..., description='mult_coef')
    limit_radius_coef: float = Field(..., description='limit_radius_coef')
    min_length_horWell: float = Field(..., description='min_length_horWell')
    water_cut: Union[float, str] = Field(..., description='water_cut')
    fluid_rate: Union[float, str] = Field(..., description='fluid_rate')
    mean_oilrate_option: str = Field(..., description='mean_oilrate_option')
    percent_oilrate: float = Field(..., description='percent_oilrate')
    limit_oilrate: Union[float, str] = Field(..., description='limit_oilrate')
    limit_research_time: str = Field(..., description='limit_research_time')
    min_research_time: Union[float, str] = Field(..., description='min_research_time')
    max_research_time: Union[float, str] = Field(..., description='max_research_time')
    option_percent: str = Field(..., description='option_percent')
    list_order_fond: str = Field(..., description='list_order_fond')
    percent_piez: float = Field(..., description='percent_piez')
    percent_inj: float = Field(..., description='percent_inj')
    percent_prod: float = Field(..., description='percent_prod')
    separation_by_years: int = Field(..., description='separation_by_years')
    max_distance: float = Field(..., description='max_distance')
    verticalWellAngle: float = Field(..., description='verticalWellAngle')
    MaxOverlapPercent: float = Field(..., description='MaxOverlapPercent')
    angle_horizontalT1: float = Field(..., description='angle_horizontalT1')
    angle_horizontalT3: float = Field(..., description='angle_horizontalT3')

    @field_validator("calc_option", "mean_oilrate_option", "limit_research_time", "option_percent",
                     mode="before")
    def boolean_params_to_str(cls, bool_to_str: bool) -> str:
        """
        Преобразование из значений типа bool в Да/Нет
        :param bool_to_str:
        :return:
        """
        if bool_to_str:
            return "Да"
        else:
            return "Нет"

    @field_validator("calculation_scenario", mode="before")
    def var_of_calc(cls, scen: str) -> str:
        if scen == "optimize":
            return "Оптимальная сетка"
        else:
            return "Регулярная сетка"

    @field_validator("gdis_option", mode="before")
    def gdis_option_validation(cls, gdis: str | None) -> str:
        """

        :param gdis:
        :return:
        """
        if gdis is not None:
            return gdis
        else:
            return ""

    @field_validator("horizon_count", mode="before")
    def hor_count_valid(cls, hor: int | str) -> int | str:
        """

        :param hor:
        :return:
        """
        if hor is not None:
            return hor
        else:
            return ""
