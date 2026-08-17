#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Cidade mais próxima do GPS via Nominatim/OpenStreetMap (gratuito, com cache local)."""

import json
import logging
import time
import urllib.request
from pathlib import Path

try:
    from .nomeacao import para_snake_case
except ImportError:
    from nomeacao import para_snake_case

DIR_RAIZ = Path(__file__).resolve().parent.parent
CACHE_GPS_PADRAO = DIR_RAIZ / "cache_gps_cidades.json"
NOMINATIM_DELAY = 1.1
USER_AGENT = "pyPhotosOrganizeTPV/1.1 (uso pessoal)"


def carregar_cache_gps(cache_path=None):
    path = Path(cache_path) if cache_path else CACHE_GPS_PADRAO
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def salvar_cache_gps(cache, cache_path=None):
    path = Path(cache_path) if cache_path else CACHE_GPS_PADRAO
    try:
        path.write_text(json.dumps(cache, ensure_ascii=False, indent=1), encoding="utf-8")
    except OSError:
        pass


def cidade_por_gps(lat, lon, cache=None, cache_path=None):
    cache = cache if cache is not None else carregar_cache_gps(cache_path)
    chave = f"{lat:.5f},{lon:.5f}"
    if chave in cache:
        return cache[chave]
    try:
        url = ("https://nominatim.openstreetmap.org/reverse?format=jsonv2"
               f"&lat={lat:.6f}&lon={lon:.6f}&zoom=10&accept-language=pt-BR,pt")
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=20) as resp:
            dados = json.loads(resp.read().decode("utf-8"))
        end = dados.get("address", {}) or {}
        cidade = (end.get("city") or end.get("town") or end.get("village")
                  or end.get("municipality") or end.get("county") or end.get("state") or "")
        if not cidade:
            cidade = dados.get("name") or ""
        cache[chave] = cidade
        salvar_cache_gps(cache, cache_path)
        time.sleep(NOMINATIM_DELAY)
        return cidade
    except Exception as e:
        logging.warning("Falha na consulta Nominatim (%s): %s", chave, e)
        return None


def cidade_ou_coordenadas(lat, lon, cache=None, cache_path=None):
    nome = cidade_por_gps(lat, lon, cache, cache_path)
    if nome:
        return para_snake_case(nome)
    return (f"{lat:.4f},{lon:.4f}".replace(",", "_").replace(".", "_").replace(" ", "_"))
