#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Cidade mais próxima do GPS via Nominatim/OpenStreetMap (gratuito, com cache local).

Fluxo:

1. Recebe latitude/longitude (extraídas dos metadados da mídia).
2. Consulta o Nominatim (OpenStreetMap) com zoom=10 para achar a cidade.
3. Guarda o resultado no cache local ``cache_gps_cidades.json`` (as
   consultas repetidas não gastam tempo nem sobrecarregam o serviço).

Política de uso do Nominatim (gratuito): 1 requisição por segundo
(NOMINATIM_DELAY) e User-Agent identificado — respeitar para não ser
bloqueado pelo serviço.
"""

import json
import logging
import time
import urllib.request
from pathlib import Path

from pereiras_common.uteis import para_snake_case

# Raiz do projeto (pasta acima do pacote py_photos_organize_tpv).
DIR_RAIZ = Path(__file__).resolve().parent.parent
CACHE_GPS_PADRAO = DIR_RAIZ / "cache_gps_cidades.json"

# Pausa entre consultas ao Nominatim (política de uso do serviço).
NOMINATIM_DELAY = 1.1
# Identificação do aplicativo nas requisições HTTP (exigido pelo OSM).
USER_AGENT = "pyPhotosOrganizeTPV/1.1 (uso pessoal)"


def carregar_cache_gps(cache_path=None):
    """Lê o cache de cidades do disco; devolve {} se não existir/corrompido."""
    path = Path(cache_path) if cache_path else CACHE_GPS_PADRAO
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def salvar_cache_gps(cache, cache_path=None):
    """Grava o cache de cidades no disco (falhas de I/O são ignoradas)."""
    path = Path(cache_path) if cache_path else CACHE_GPS_PADRAO
    try:
        path.write_text(json.dumps(cache, ensure_ascii=False, indent=1), encoding="utf-8")
    except OSError:
        pass


def cidade_por_gps(lat, lon, cache=None, cache_path=None):
    """Devolve o nome da cidade mais próxima das coordenadas.

    - Se as coordenadas já estão no cache, devolve direto (sem internet).
    - Senão, consulta o Nominatim, salva no cache e devolve o nome.
    - Em caso de falha (sem internet etc.), devolve None e NÃO polui o
      cache (uma execução futura pode tentar de novo).
    """
    cache = cache if cache is not None else carregar_cache_gps(cache_path)
    # Chave com 5 casas decimais: mesma rua = mesma chave = mesma consulta.
    chave = f"{lat:.5f},{lon:.5f}"
    if chave in cache:
        return cache[chave]
    try:
        # Consulta reversa: coordenadas -> endereço (zoom 10 ~ nível de cidade).
        url = ("https://nominatim.openstreetmap.org/reverse?format=jsonv2"
               f"&lat={lat:.6f}&lon={lon:.6f}&zoom=10&accept-language=pt-BR,pt")
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=20) as resp:
            dados = json.loads(resp.read().decode("utf-8"))
        end = dados.get("address", {}) or {}
        # Tenta os campos de cidade do mais específico ao mais genérico.
        cidade = (end.get("city") or end.get("town") or end.get("village")
                  or end.get("municipality") or end.get("county") or end.get("state") or "")
        if not cidade:
            cidade = dados.get("name") or ""
        cache[chave] = cidade
        salvar_cache_gps(cache, cache_path)
        # Respeita a política de uso do Nominatim: no máximo ~1 req/s.
        time.sleep(NOMINATIM_DELAY)
        return cidade
    except Exception as e:
        logging.warning("Falha na consulta Nominatim (%s): %s", chave, e)
        return None


def cidade_ou_coordenadas(lat, lon, cache=None, cache_path=None):
    """Devolve o nome da cidade em snake_case ou as coordenadas no formato do nome alvo.

    - Com cidade: "sao_paulo" (pronta para compor o nome do arquivo).
    - Sem cidade (falha/offline): "-23_5500_-46_6333" (coordenadas com
      "_" no lugar de pontos e vírgulas, sem caracteres especiais).
    """
    nome = cidade_por_gps(lat, lon, cache, cache_path)
    if nome:
        return para_snake_case(nome)
    return (f"{lat:.4f},{lon:.4f}".replace(",", "_").replace(".", "_").replace(" ", "_"))
