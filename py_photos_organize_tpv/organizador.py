#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Núcleo do organizador: varre a pasta de origem e gera os arquivos
organizados em subpastas por data, com o nome no formato alvo
{data1}-{data2}-{cidade}-{titulo}-{hash6}{ext}.

Fluxo de cada arquivo (processar_arquivo):

1. Coleta datas e GPS (metadados -> nome do arquivo -> sistema de arquivos).
2. Classifica um sufixo de pasta (videos, audios, social_media...).
3. Gera o título por IA (se habilitada) e a cidade pelo GPS.
4. Calcula o hash curto do conteúdo (identificação/deduplicação).
5. Monta o nome alvo e copia/move para a pasta de destino.

Estruturas de dados:

- Config: parâmetros de uma execução (pastas, opções, chaves).
- Estatisticas: contadores exibidos no resumo final.
"""

import logging
import shutil
from dataclasses import dataclass
from pathlib import Path

from pereiras_common import metadados
from pereiras_common.uteis import hash_curto_6

from . import geolocalizacao, ia
from .nomeacao import dentro_do_periodo, extrair_data_nome, montar_novo_nome


@dataclass
class Config:
    """Parâmetros de uma execução do organizador (preenchidos pelo CLI)."""
    origem: Path
    destino: Path
    folders_mask: str = "%Y_%m"
    overwrite: str = "d"
    batch: int = 0
    ano_minimo: int = 1980
    min_size_low_res: int = 100000
    gerar_sufixo: bool = True
    renomear: bool = True
    usar_ia: bool = True
    dry_run: bool = False
    mover: bool = False
    frames: int = 5
    chave_gemini: str | None = None
    chave_openai: str | None = None
    cache_titulos_path: str | None = None
    cache_gps_path: str | None = None


@dataclass
class Estatisticas:
    """Contadores do processamento, exibidos no resumo final."""
    total: int = 0
    copiados: int = 0
    movidos: int = 0
    ignorados: int = 0
    sem_data: int = 0
    erros: int = 0


def coletar_arquivos(origem: Path) -> list[Path]:
    """Lista os arquivos suportados dentro da pasta de origem (recursivo).

    Só entram arquivos com extensão conhecida (ALL_EXTENSIONS do pacote
    compartilhado). A lista é ordenada para processamento determinístico.
    """
    arquivos = [
        p for p in origem.rglob("*")
        if p.is_file() and p.suffix.lower() in metadados.ALL_EXTENSIONS
    ]
    return sorted(arquivos, key=lambda p: str(p).lower())


def classificar_sufixo(caminho: Path, tamanho: int | None, min_size_low_res: int) -> str | None:
    """Classifica o sufixo de pasta pela extensão, nome e tamanho.

    Ex.: "video.mp4" -> "videos"; "Screenshot_1.jpg" -> "screen_capture";
    arquivos pequenos -> "low_resolution". None = sem sufixo.
    """
    nome = caminho.name.lower()
    ext = caminho.suffix.lower()
    if ext in metadados.EXTS_VIDEO:
        return "videos"
    if ext in metadados.EXTS_AUDIO:
        return "audios"
    if ext in metadados.EXTS_OFFICE:
        return "office"
    if ext in metadados.EXTS_OUTROS:
        return "outros_tipos"
    if any(k in nome for k in ("screenshot", "screen", "capture")):
        return "screen_capture"
    if any(k in nome for k in ("insta", "facebook", "tiktok", "twitter", "social")):
        return "social_media"
    if any(k in nome for k in ("whats", "telegram", "message", "instant", "img-", "wa0")):
        return "instant_messages"
    if tamanho is not None and min_size_low_res > 0 and tamanho < min_size_low_res:
        return "low_resolution"
    return None


def obter_datas(caminho: Path, ano_minimo: int):
    """Retorna (data_min, data_max, gps) pelas fontes, em ordem de prioridade.

    1. Metadados embutidos (EXIF/XMP/PNG para imagens; ffmpeg/mutagen para
       vídeos; ID3/MP4/Vorbis para áudios), com fallback exiftool.
    2. Nome do arquivo (várias máscaras de data).
    3. Sistema de arquivos (data de criação/modificação).

    data_min/data_max podem ser iguais (uma única data encontrada) ou
    None (nenhuma data válida).
    """
    fontes = []
    gps = None
    ext = caminho.suffix.lower()
    if ext in metadados.EXTS_IMAGEM:
        # Imagens: podem ter várias datas (EXIF + XMP); usamos min e max.
        datas_meta, gps = metadados.metadados_imagem(caminho)
        if not datas_meta and gps is None:
            datas_meta, gps = metadados.metadados_exiftool(caminho)
        if datas_meta:
            validas = [d for d in datas_meta if dentro_do_periodo(d, ano_minimo)]
            if validas:
                fontes.append(("metadados", min(validas)))
    elif ext in metadados.EXTS_VIDEO:
        # Vídeos: uma única data (creation_time do container).
        dt, gps = metadados.metadados_video(caminho)
        if dt is None and gps is None:
            dt, gps = metadados.metadados_exiftool(caminho)
        if dt and dentro_do_periodo(dt, ano_minimo):
            fontes.append(("metadados", dt))
    elif ext in metadados.EXTS_AUDIO:
        # Áudios: datas das tags (ID3/©day/Vorbis), com fallback exiftool.
        datas_meta, gps = metadados.metadados_audio(caminho)
        if not datas_meta and gps is None:
            datas_meta, gps = metadados.metadados_exiftool(caminho)
        if datas_meta:
            validas = [d for d in datas_meta if dentro_do_periodo(d, ano_minimo)]
            if validas:
                fontes.append(("metadados", min(validas)))
    dt_nome = extrair_data_nome(caminho.stem, ano_minimo)
    if dt_nome:
        fontes.append(("nome", dt_nome))
    if not fontes:
        dt_fs = metadados.data_filesystem(caminho)
        if dt_fs and dentro_do_periodo(dt_fs, ano_minimo):
            fontes.append(("sistema", dt_fs))
    if not fontes:
        return None, None, gps
    datas = [dt for _, dt in fontes]
    return min(datas), max(datas), gps


def montar_pasta_destino(destino: Path, dt, mask: str, sufixo: str | None) -> Path:
    """Monta a subpasta de destino: {data_formatada}-{sufixo} (ou "sem_data")."""
    if dt is None:
        return destino / "sem_data"
    nome = dt.strftime(mask)
    if sufixo:
        nome = f"{nome}-{sufixo}"
    return destino / nome


def proximo_livre(alvo: Path) -> Path:
    """Devolve um nome livre acrescentando _2, _3, ... quando o alvo já existe."""
    contador = 2
    while alvo.exists():
        alvo = alvo.with_name(f"{alvo.stem}_{contador}{alvo.suffix}")
        contador += 1
    return alvo


def processar_arquivo(caminho: Path, cfg: Config, contexto, cache_titulos, cache_gps, estats: Estatisticas):
    """Processa UM arquivo: define nome/pasta alvo e copia ou move.

    Ordem interna:

    1. Obtém datas/GPS (obter_datas) e sufixo de pasta.
    2. Se renomear habilitado: gera título (IA), cidade (GPS) e hash
       curto; monta o nome alvo.
    3. Resolve conflito de nome existente (duplicar/ignorar/sobrescrever).
    4. Executa a ação (copiar/mover), respeitando o dry-run.
    """
    try:
        tamanho = caminho.stat().st_size
    except OSError:
        tamanho = None
    ext = caminho.suffix.lower()
    if ext in metadados.EXTS_IMAGEM:
        tipo = "imagem"
    elif ext in metadados.EXTS_VIDEO:
        tipo = "video"
    else:
        tipo = "outro"

    d_min, d_max, gps = obter_datas(caminho, cfg.ano_minimo)
    sufixo = classificar_sufixo(caminho, tamanho, cfg.min_size_low_res) if cfg.gerar_sufixo else None
    pasta = montar_pasta_destino(cfg.destino, d_min, cfg.folders_mask, sufixo)

    if d_min is not None and cfg.renomear:
        titulo = ia.obter_titulo(caminho, tipo, contexto["ia"], cache_titulos,
                                 contexto["cache_titulos_path"], cfg.frames)
        cidade = (geolocalizacao.cidade_ou_coordenadas(gps[0], gps[1], cache_gps,
                                                       contexto["cache_gps_path"])
                  if gps else "sem_gps")
        # Hash curto do conteúdo: identifica o arquivo e evita nomes
        # duplicados quando há cópias do mesmo arquivo na origem.
        hash6 = hash_curto_6(caminho)
        novo_nome = montar_novo_nome(d_min, d_max, cidade, titulo, ext, hash6)
        if novo_nome is None:
            logging.warning("Nome alvo muito longo (%s); mantendo nome original.",
                            caminho.name)
            novo_nome = caminho.name
    else:
        if d_min is None:
            estats.sem_data += 1
            logging.info("SEM DATA (mantendo nome original; pasta sem_data): %s", caminho)
        novo_nome = caminho.name

    alvo = pasta / novo_nome
    if alvo.resolve() == caminho.resolve():
        logging.info("INALTERADO (já está no destino e no formato alvo): %s", caminho)
        return

    if alvo.exists():
        if cfg.overwrite == "i":
            estats.ignorados += 1
            logging.info("IGNORADO (já existe no destino): %s -> %s", caminho, alvo)
            return
        if cfg.overwrite != "o":
            alvo = proximo_livre(alvo)

    acao = "MOVER" if cfg.mover else "COPIAR"
    if cfg.dry_run:
        logging.info("%s (dry-run): %s -> %s", acao, caminho, alvo)
        estats.copiados += 1
        return
    try:
        pasta.mkdir(parents=True, exist_ok=True)
        if cfg.mover:
            shutil.move(str(caminho), str(alvo))
            estats.movidos += 1
        else:
            shutil.copy2(caminho, alvo)
            estats.copiados += 1
        logging.info("%s: %s -> %s", acao, caminho, alvo)
    except OSError as e:
        estats.erros += 1
        logging.error("ERRO ao %s %s -> %s (%s)",
                      "mover" if cfg.mover else "copiar", caminho, alvo, e)


def organizar(cfg: Config) -> Estatisticas:
    """Executa o organizador completo na pasta de origem.

    - Prepara o contexto de IA (se habilitada) e os caches.
    - Processa os arquivos um a um, com log de progresso.
    - Devolve as estatísticas (total, copiados, movidos, ignorados, erros).
    """
    estats = Estatisticas()
    arquivos = coletar_arquivos(cfg.origem)
    if cfg.batch > 0:
        arquivos = arquivos[:cfg.batch]
    estats.total = len(arquivos)
    logging.info("Arquivos encontrados para organizar: %d.", estats.total)

    contexto = {
        "ia": None,
        "cache_titulos_path": cfg.cache_titulos_path or ia.CACHE_TITULOS_PADRAO,
        "cache_gps_path": cfg.cache_gps_path or geolocalizacao.CACHE_GPS_PADRAO,
    }
    if cfg.usar_ia:
        contexto["ia"] = ia.criar_contexto_ia(cfg.chave_gemini, cfg.chave_openai)
    cache_titulos = ia.carregar_cache_titulos(contexto["cache_titulos_path"])
    cache_gps = geolocalizacao.carregar_cache_gps(contexto["cache_gps_path"])

    for n, caminho in enumerate(arquivos, 1):
        logging.info("")
        logging.info("[%d/%d] Processando: %s", n, estats.total, caminho)
        processar_arquivo(caminho, cfg, contexto, cache_titulos, cache_gps, estats)
    return estats
