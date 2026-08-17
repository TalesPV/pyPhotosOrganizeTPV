#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Testes das funções de datas e nomeação."""

from datetime import datetime

import pytest

from py_photos_organize_tpv.nomeacao import (
    MAX_COMPRIMENTO_NOME,
    extrair_data_nome,
    formatar_data,
    montar_dt,
    montar_novo_nome,
    para_snake_case,
    parsear_data_exif,
    titulo_valido,
)


def test_para_snake_case_acentos():
    assert para_snake_case("São Paulo") == "sao_paulo"
    assert para_snake_case("Foto 01 - Praia!") == "foto_01_praia"
    assert para_snake_case("çamarões") == "camaroes"
    assert para_snake_case("!!!") == "sem_nome"


def test_titulo_valido():
    assert titulo_valido("festa_de_aniversario")
    assert not titulo_valido("Festa Aniversário")
    assert not titulo_valido("")
    assert not titulo_valido("com espaço")


def test_formatar_data():
    dt = datetime(2023, 5, 10, 14, 30, 5)
    assert formatar_data(dt) == "2023_05_10_14h30m05s"


def test_montar_dt_invalido():
    assert montar_dt(2023, 2, 30) is None
    assert montar_dt(1970, 1, 1) is None
    assert montar_dt(3000, 1, 1) is None


@pytest.mark.parametrize("nome,esperado", [
    ("foto_2019_07_04_08h09m10s.jpg", datetime(2019, 7, 4, 8, 9, 10)),
    ("IMG_20190315102030.jpg", datetime(2019, 3, 15, 10, 20, 30)),
    ("video-2018-12-25_23-59-58.mp4", datetime(2018, 12, 25, 23, 59, 58)),
    ("antiga_2021_01_02.jpg", datetime(2021, 1, 2)),
    ("foto_2021_03_15.jpg", datetime(2021, 3, 15)),
    ("jan_02_2020.jpg", datetime(2020, 1, 2)),
    ("02 jan 2020.jpg", datetime(2020, 1, 2)),
])
def test_extrair_data_nome_mascaras(nome, esperado):
    assert extrair_data_nome(nome) == esperado


def test_extrair_data_nome_prefere_precisa():
    nome = "2019_07_04_08h09m10s_2019_07_05_00h00m00s.jpg"
    assert extrair_data_nome(nome) == datetime(2019, 7, 4, 8, 9, 10)


def test_extrair_data_nome_sem_data():
    assert extrair_data_nome("foto_da_praia.jpg") is None


def test_extrair_data_nome_ano_minimo():
    assert extrair_data_nome("foto_1950_01_01.jpg", ano_minimo=1980) is None


def test_parsear_data_exif():
    assert parsear_data_exif("2021:03:15 10:20:30") == datetime(2021, 3, 15, 10, 20, 30)
    assert parsear_data_exif("2021-03-15T10:20:30") == datetime(2021, 3, 15, 10, 20, 30)
    assert parsear_data_exif("data qualquer") is None


def test_montar_novo_nome():
    d1 = datetime(2020, 1, 2, 3, 4, 5)
    d2 = datetime(2021, 6, 7, 8, 9, 10)
    nome = montar_novo_nome(d1, d2, "rio_de_janeiro", "festa_de_aniversario", ".jpg")
    assert nome == ("2020_01_02_03h04m05s-2021_06_07_08h09m10s-"
                    "rio_de_janeiro-festa_de_aniversario.jpg")


def test_montar_novo_nome_sem_titulo():
    d1 = datetime(2020, 1, 2, 3, 4, 5)
    d2 = datetime(2021, 6, 7, 8, 9, 10)
    nome = montar_novo_nome(d1, d2, "sao_paulo", "", ".jpg")
    assert nome == "2020_01_02_03h04m05s-2021_06_07_08h09m10s-sao_paulo.jpg"
    nome_none = montar_novo_nome(d1, d2, "sem_gps", None, ".jpg")
    assert nome_none == "2020_01_02_03h04m05s-2021_06_07_08h09m10s-sem_gps.jpg"


def test_montar_novo_nome_data_unica():
    d = datetime(2020, 1, 2, 3, 4, 5)
    nome = montar_novo_nome(d, d, "sem_gps", "foto", ".jpg")
    assert nome == "2020_01_02_03h04m05s-2020_01_02_03h04m05s-sem_gps-foto.jpg"


def test_montar_novo_nome_muito_longo():
    d = datetime(2020, 1, 2, 3, 4, 5)
    titulo = "_".join(["palavra"] * 60)
    assert montar_novo_nome(d, d, "cidade", titulo, ".jpg") is None
    assert MAX_COMPRIMENTO_NOME == 240
