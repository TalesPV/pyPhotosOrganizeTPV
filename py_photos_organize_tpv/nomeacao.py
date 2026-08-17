#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Funções de datas e nomeação.

Formato alvo do nome gerado (igual ao renomear_arquivos.py):
    {data1}-{data2}-{cidade}-{titulo}{ext}

- data1 é a data mais antiga e data2 a mais recente (se houver uma só,
  ela se repete nos dois blocos), com máscara YYYY_MM_DD_HHhMMmSSs.
- cidade é o nome da cidade do GPS em snake_case, "sem_gps" ou coordenadas.
- titulo é um título em snake_case gerado por IA. Quando a IA está
  desativada ou indisponível, o bloco {titulo} é omitido do nome:
  {data1}-{data2}-{cidade}{ext}.
"""

import re
import unicodedata
from datetime import datetime

ANO_MINIMO_PADRAO = 1980
MAX_COMPRIMENTO_NOME = 240

MESES = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
    "fev": 2, "abr": 4, "mai": 5, "ago": 8, "set": 9, "out": 10, "dez": 12,
}

RE_TITULO = re.compile(r"^[a-z0-9]+(?:_[a-z0-9]+)*$")


def para_snake_case(texto):
    texto = unicodedata.normalize("NFKD", str(texto))
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    texto = re.sub(r"[^a-zA-Z0-9]+", "_", texto).strip("_").lower()
    return texto or "sem_nome"


def titulo_valido(titulo):
    return bool(titulo) and bool(RE_TITULO.match(str(titulo)))


def dentro_do_periodo(dt, ano_minimo=ANO_MINIMO_PADRAO):
    return dt is not None and ano_minimo <= dt.year and dt <= datetime.now()


def montar_dt(ano, mes, dia, hora=0, minuto=0, segundo=0, ano_minimo=ANO_MINIMO_PADRAO):
    try:
        dt = datetime(int(ano), int(mes), int(dia), int(hora), int(minuto), int(segundo))
    except (ValueError, TypeError):
        return None
    return dt if dentro_do_periodo(dt, ano_minimo) else None


def formatar_data(dt):
    return (f"{dt.year:04d}_{dt.month:02d}_{dt.day:02d}_"
            f"{dt.hour:02d}h{dt.minute:02d}m{dt.second:02d}s")


def montar_novo_nome(d_min, d_max, cidade, titulo, extensao):
    """Monta o nome alvo {data1}-{data2}-{cidade}-{titulo}{ext}.

    Se o título estiver vazio (IA desativada ou indisponível), o bloco
    {titulo} é omitido: {data1}-{data2}-{cidade}{ext}.
    Retorna None se o nome resultante exceder MAX_COMPRIMENTO_NOME.
    """
    base = f"{formatar_data(d_min)}-{formatar_data(d_max)}-{cidade}"
    if titulo:
        base = f"{base}-{titulo}"
    nome = f"{base}{extensao}"
    if len(nome) > MAX_COMPRIMENTO_NOME:
        return None
    return nome


def extrair_data_nome(nome, ano_minimo=ANO_MINIMO_PADRAO):
    """Extrai a data mais provável do nome do arquivo.

    Várias máscaras são tentadas (YYYY_MM_DD_HHhMMmSSs, YYYYMMDDhhmmss,
    DDMMYYYY, MMDDYYYY, ISO, MMM_DD_YYYY etc.). Entre os candidatos válidos,
    prefere-se o mais antigo que tenha horário real (evita 00:00:00).
    """
    candidatos = []

    def adicionar(dt):
        if dt is not None:
            preciso = not (dt.hour == 0 and dt.minute == 0 and dt.second == 0)
            candidatos.append((dt, preciso))

    for m in re.finditer(r"(?<!\d)(\d{4})_(\d{2})_(\d{2})_(\d{2})h(\d{2})m(\d{2})s", nome):
        adicionar(montar_dt(*m.groups(), ano_minimo=ano_minimo))
    for m in re.finditer(r"(?<!\d)(\d{4})_(\d{2})_(\d{2})_(\d{2})_(\d{2})_(\d{2})(?!\d)", nome):
        adicionar(montar_dt(*m.groups(), ano_minimo=ano_minimo))
    for m in re.finditer(r"(?<!\d)(\d{4})(\d{2})(\d{2})\D?([0-1]\d|2[0-4])([0-5]\d)([0-5]\d)(?!\d)", nome):
        adicionar(montar_dt(*m.groups(), ano_minimo=ano_minimo))
    for m in re.finditer(r"(?<!\d)(\d{4})-(\d{2})-(\d{2})[ T_-](\d{2})[.:-](\d{2})(?:[.:-](\d{2}))?(?!\d)", nome):
        adicionar(montar_dt(m.group(1), m.group(2), m.group(3), m.group(4), m.group(5),
                            m.group(6) or 0, ano_minimo=ano_minimo))
    for m in re.finditer(r"(?<!\d)(0[1-9]|[1-2]\d|3[0-1])\D(0[1-9]|1[0-2])\D(19[7-9]\d|20[0-2]\d)\D([0-1]\d|2[0-4])\D([0-5]\d)\D([0-5]\d)(?!\d)", nome):
        adicionar(montar_dt(m.group(3), m.group(2), m.group(1), m.group(4), m.group(5),
                            m.group(6), ano_minimo=ano_minimo))
    for m in re.finditer(r"(?<!\d)(0[1-9]|[1-2]\d|3[0-1])(0[1-9]|1[0-2])(19[7-9]\d|20[0-2]\d)\D?([0-1]\d|2[0-4])([0-5]\d)([0-5]\d)(?!\d)", nome):
        adicionar(montar_dt(m.group(3), m.group(2), m.group(1), m.group(4), m.group(5),
                            m.group(6), ano_minimo=ano_minimo))
    for m in re.finditer(r"(?<!\d)(0[1-9]|1[0-2])\D(0[1-9]|[1-2]\d|3[0-1])\D(19[7-9]\d|20[0-2]\d)\D([0-1]\d|2[0-4])\D([0-5]\d)\D([0-5]\d)(?!\d)", nome):
        adicionar(montar_dt(m.group(3), m.group(1), m.group(2), m.group(4), m.group(5),
                            m.group(6), ano_minimo=ano_minimo))
    for m in re.finditer(r"(?<!\d)(0[1-9]|1[0-2])(0[1-9]|[1-2]\d|3[0-1])(19[7-9]\d|20[0-2]\d)\D?([0-1]\d|2[0-4])([0-5]\d)([0-5]\d)(?!\d)", nome):
        adicionar(montar_dt(m.group(3), m.group(1), m.group(2), m.group(4), m.group(5),
                            m.group(6), ano_minimo=ano_minimo))
    for m in re.finditer(r"(?<!\d)(\d{4})_(\d{2})_(\d{2})(?!\d)", nome):
        adicionar(montar_dt(*m.groups(), ano_minimo=ano_minimo))
    for m in re.finditer(r"(?<!\d)(\d{4})-(\d{2})-(\d{2})(?!\d)", nome):
        adicionar(montar_dt(*m.groups(), ano_minimo=ano_minimo))
    for m in re.finditer(r"(?<!\d)(\d{4})(\d{2})(\d{2})(?!\d)", nome):
        adicionar(montar_dt(*m.groups(), ano_minimo=ano_minimo))
    for m in re.finditer(r"\b([A-Za-z]{3})[ _.\-](\d{1,2})[ _.\-](\d{4})\b", nome):
        mes = MESES.get(m.group(1).lower())
        if mes:
            adicionar(montar_dt(m.group(3), mes, m.group(2), ano_minimo=ano_minimo))
    for m in re.finditer(r"\b(\d{1,2})[ _.\-]([A-Za-z]{3})[ _.\-](\d{4})\b", nome):
        mes = MESES.get(m.group(2).lower())
        if mes:
            adicionar(montar_dt(m.group(3), mes, m.group(1), ano_minimo=ano_minimo))

    if not candidatos:
        return None
    precisos = [dt for dt, p in candidatos if p]
    pool = precisos or [dt for dt, _ in candidatos]
    return min(pool)


def parsear_data_exif(texto, ano_minimo=ANO_MINIMO_PADRAO):
    s = str(texto).strip()
    s = s.replace("-", ":").replace("_", ":").replace("T", " ")
    s = re.sub(r"\s+", " ", s)
    m = re.match(r"(\d{4}):(\d{2}):(\d{2})[ T](\d{2}):(\d{2}):(\d{2})", s)
    if not m:
        return None
    return montar_dt(*m.groups(), ano_minimo=ano_minimo)
