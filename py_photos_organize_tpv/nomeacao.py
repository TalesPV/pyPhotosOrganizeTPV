#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Funções de datas e nomeação (pyPhotosOrganizeTPV).

Formato alvo do nome gerado:

    {data1}-{data2}-{cidade}-{titulo}-{hash6}{ext}

- data1 é a data mais antiga e data2 a mais recente (se houver uma só,
  ela se repete nos dois blocos), com máscara YYYY_MM_DD_HHhMMmSSs.
- cidade é o nome da cidade do GPS em snake_case, "sem_gps" ou coordenadas.
- titulo é um título em snake_case gerado por IA. Quando a IA está
  desativada ou indisponível, o bloco {titulo} é omitido do nome.
- hash6 é um hash curto (6 caracteres alfanuméricos) do conteúdo do
  arquivo, calculado por pereiras_common.uteis.hash_curto_6. Ele
  identifica o conteúdo e evita nomes duplicados em coleções com
  cópias do mesmo arquivo.
"""

import re
from datetime import datetime

from pereiras_common.uteis import para_snake_case  # noqa: F401  (re-exportado)

# Ano mais antigo aceito nas datas (arquivos anteriores são ignorados).
ANO_MINIMO_PADRAO = 1980

# Limite de tamanho do nome gerado (segurança para sistemas de arquivos).
MAX_COMPRIMENTO_NOME = 240

# Abreviações de meses aceitas no nome do arquivo (PT e EN).
MESES = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
    "fev": 2, "abr": 4, "mai": 5, "ago": 8, "set": 9, "out": 10, "dez": 12,
}

# Um título válido tem apenas letras minúsculas, números e "_".
RE_TITULO = re.compile(r"^[a-z0-9]+(?:_[a-z0-9]+)*$")


def titulo_valido(titulo: object) -> bool:
    """Indica se o título respeita o formato snake_case do nome alvo.

    Ex.: "festa_de_aniversario" é válido; "Festa Aniversário" não.
    """
    return bool(titulo) and bool(RE_TITULO.match(str(titulo)))


def dentro_do_periodo(dt, ano_minimo: int = ANO_MINIMO_PADRAO) -> bool:
    """Indica se a data é plausível (não nula, não antiga demais, não futura)."""
    return dt is not None and ano_minimo <= dt.year and dt <= datetime.now()


def montar_dt(ano, mes, dia, hora=0, minuto=0, segundo=0, ano_minimo=ANO_MINIMO_PADRAO):
    """Monta um datetime validado; devolve None se a data for inválida."""
    try:
        dt = datetime(int(ano), int(mes), int(dia), int(hora), int(minuto), int(segundo))
    except (ValueError, TypeError):
        return None
    return dt if dentro_do_periodo(dt, ano_minimo) else None


def formatar_data(dt) -> str:
    """Formata um datetime na máscara do nome alvo: YYYY_MM_DD_HHhMMmSSs."""
    return (f"{dt.year:04d}_{dt.month:02d}_{dt.day:02d}_"
            f"{dt.hour:02d}h{dt.minute:02d}m{dt.second:02d}s")


def montar_novo_nome(d_min, d_max, cidade, titulo, extensao, hash_curto=None):
    """Monta o nome alvo {data1}-{data2}-{cidade}-{titulo}-{hash6}{ext}.

    Regras:

    - Se o título estiver vazio (IA desativada ou indisponível), o bloco
      {titulo} é omitido do nome.
    - Se hash_curto for informado, ele é anexado antes da extensão.
    - Retorna None se o nome resultante exceder MAX_COMPRIMENTO_NOME.

    Exemplos::

        montar_novo_nome(d1, d2, "sao_paulo", "festa", ".jpg", "k3x9ab")
        # -> "2020_01_02_03h04m05s-2021_06_07_08h09m10s-sao_paulo-festa-k3x9ab.jpg"
    """
    base = f"{formatar_data(d_min)}-{formatar_data(d_max)}-{cidade}"
    if titulo:
        base = f"{base}-{titulo}"
    if hash_curto:
        base = f"{base}-{hash_curto}"
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
        """Registra um candidato, marcando se tem horário real (não 00:00:00)."""
        if dt is not None:
            preciso = not (dt.hour == 0 and dt.minute == 0 and dt.second == 0)
            candidatos.append((dt, preciso))

    # Máscaras com horário completo (mais confiáveis são testadas primeiro).
    for m in re.finditer(r"(?<!\d)(\d{4})_(\d{2})_(\d{2})_(\d{2})h(\d{2})m(\d{2})s", nome):
        adicionar(montar_dt(*m.groups(), ano_minimo=ano_minimo))
    for m in re.finditer(r"(?<!\d)(\d{4})_(\d{2})_(\d{2})_(\d{2})_(\d{2})_(\d{2})(?!\d)", nome):
        adicionar(montar_dt(*m.groups(), ano_minimo=ano_minimo))
    for m in re.finditer(r"(?<!\d)(\d{4})(\d{2})(\d{2})\D?([0-1]\d|2[0-4])([0-5]\d)([0-5]\d)(?!\d)", nome):
        adicionar(montar_dt(*m.groups(), ano_minimo=ano_minimo))
    for m in re.finditer(r"(?<!\d)(\d{4})-(\d{2})-(\d{2})[ T_-](\d{2})[.:-](\d{2})(?:[.:-](\d{2}))?(?!\d)", nome):
        adicionar(montar_dt(m.group(1), m.group(2), m.group(3), m.group(4), m.group(5),
                            m.group(6) or 0, ano_minimo=ano_minimo))
    # Máscaras dia/mês/ano com horário.
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
    # Máscaras só com data (sem horário).
    for m in re.finditer(r"(?<!\d)(\d{4})_(\d{2})_(\d{2})(?!\d)", nome):
        adicionar(montar_dt(*m.groups(), ano_minimo=ano_minimo))
    for m in re.finditer(r"(?<!\d)(\d{4})-(\d{2})-(\d{2})(?!\d)", nome):
        adicionar(montar_dt(*m.groups(), ano_minimo=ano_minimo))
    for m in re.finditer(r"(?<!\d)(\d{4})(\d{2})(\d{2})(?!\d)", nome):
        adicionar(montar_dt(*m.groups(), ano_minimo=ano_minimo))
    # Máscaras com mês por extenso (jan_02_2020, 02 jan 2020).
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
    # Prefere datas com horário real; entre elas, a mais antiga.
    precisos = [dt for dt, p in candidatos if p]
    pool = precisos or [dt for dt, _ in candidatos]
    return min(pool)


def parsear_data_exif(texto, ano_minimo=ANO_MINIMO_PADRAO):
    """Parseia o formato clássico do EXIF: "YYYY:MM:DD HH:MM:SS".

    Aceita variações comuns ("YYYY-MM-DDTHH:MM:SS", underscores etc.).
    """
    s = str(texto).strip()
    s = s.replace("-", ":").replace("_", ":").replace("T", " ")
    s = re.sub(r"\s+", " ", s)
    m = re.match(r"(\d{4}):(\d{2}):(\d{2})[ T](\d{2}):(\d{2}):(\d{2})", s)
    if not m:
        return None
    return montar_dt(*m.groups(), ano_minimo=ano_minimo)
