#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Núcleo do organizador: varre a pasta de origem e gera os arquivos
organizados em subpastas por data, com o nome padrão das mídias:

    YYYY_MM_DD_HHhMMmSSs-YYYY_MM_DD_HHhMMmSSs-cidade-hash6-titulo.ext

Regras de nomeação (detalhadas em pereiras_common.nomeacao):

- Somente MÍDIAS (fotos, vídeos e áudios) são renomeadas; os demais
  arquivos (office, PDFs etc.) mantêm o nome original.
- Sem IA (ou com falha), o bloco {titulo} é omitido; o hash permanece
  (identifica o conteúdo e evita sobrescrita de arquivos do mesmo horário).
- Se o arquivo JÁ tem um título no nome e não há título novo, o nome
  original é mantido (preservar_nome_original): renomear apagaria uma
  informação que só uma nova chamada de IA saberia recriar.
- O relatório de classificação (.gemini_36_flash.md) acompanha a mídia:
  separá-los deixaria órfã uma análise que custou dinheiro de API.
- Sufixos automáticos de pasta são OPT-IN (--com-autosufixo-pastas; o
  -g/--generate-folder-sufix antigo continua aceito). Quando ativos, a
  pasta de data ganha o sufixo na ordem: extensão (videos/audios/office/
  outros_tipos), nome (screen_capture/social_media/instant_messages),
  fonte da data (metadados) e tamanho (low_resolution) — comportamento
  das versões antigas, com o -metadados restaurado.

Fluxo de cada arquivo (processar_arquivo):

1. Coleta datas e GPS (pereiras_common.metadados.obter_datas).
2. Classifica um sufixo de pasta (calcular_sufixo_pasta).
3. Gera o título por IA (se habilitada) e a cidade pelo GPS.
4. Calcula o hash curto do conteúdo (pereiras_common.uteis.hash_curto_6).
5. Monta o nome alvo (pereiras_common.nomeacao.montar_nome_midia) e
   copia/move para a pasta de destino.

Estruturas de dados:

- Config: parâmetros de uma execução (pastas, opções, chaves).
- Estatisticas: contadores exibidos no resumo final.
"""

import logging
import shutil
from dataclasses import dataclass
from pathlib import Path

from pereiras_common import geolocalizacao, metadados
from pereiras_common.nomeacao import (
    extrair_data_nome,
    montar_nome_midia,
    montar_pasta_destino,
    preservar_nome_original,
)
from pereiras_common.uteis import hash_curto_6, sha256_arquivo

from . import ia

# Raiz do projeto (usada nos caminhos padrão dos caches).
DIR_RAIZ = Path(__file__).resolve().parent.parent

# Tipos de arquivo que são RENOMEADOS (os demais mantêm o nome original).
TIPOS_MIDIA = {"imagem", "video", "audio"}

# Sufixo de pasta das versões antigas, quando a data vem de metadados
# embutidos (EXIF/XMP/ffmpeg/mutagen). Restaurado via --com-autosufixo-pastas.
SUFIXO_METADADOS = "metadados"

# Relatório de classificação gravado pelo verificar_fotos_videos ao lado de
# cada mídia. Ele NÃO é uma mídia (não entra na varredura nem é renomeado),
# mas precisa acompanhar o arquivo: separá-lo da foto joga fora uma análise
# que custou dinheiro de API.
EXT_SIDECAR = ".gemini_36_flash.md"


@dataclass
class Config:
    """Parâmetros de uma execução do organizador (preenchidos pelo CLI).

    ``usar_ia`` e ``gerar_sufixo`` são OPT-IN: construções diretas da
    Config (uso como biblioteca) não ligam nenhum dos dois sozinhas,
    preservando o padrão de segurança da linha de comando.
    """
    origem: Path
    destino: Path
    folders_mask: str = "%Y_%m"
    overwrite: str = "d"
    batch: int = 0
    ano_minimo: int = 1980
    min_size_low_res: int = 100000
    gerar_sufixo: bool = False
    renomear: bool = True
    usar_ia: bool = False
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


def classificar_tipo_arquivo(caminho: Path) -> str:
    """Classifica o arquivo em "imagem", "video", "audio" ou "outro".

    Delega a ``pereiras_common.metadados.classificar_tipo`` (fonte única
    das extensões) e colapsa em "outro" tudo que não é mídia — que é a
    única distinção que interessa aqui: só mídias são renomeadas.
    """
    tipo = metadados.classificar_tipo(caminho)
    return tipo if tipo in TIPOS_MIDIA else "outro"


def _data_veio_de_metadados(caminho: Path, d_min, ano_minimo: int) -> bool:
    """Indica se a data mínima veio de metadados embutidos (sufixo -metadados).

    Heurística barata (regex no nome + stat no sistema de arquivos), sem
    reler o arquivo: a data é de metadados quando NÃO é explicada nem pelo
    nome nem pela data do sistema de arquivos — exatamente as outras duas
    fontes que ``obter_datas`` consulta.

    Regras:

    - sem data -> False;
    - data igual à do nome -> False (o nome explica; empate preserva o
      comportamento idempotente: um arquivo já organizado, que tem a data
      no nome, não muda de pasta entre execuções);
    - data anterior à do nome -> True (só os metadados explicam);
    - sem data no nome, a data do sistema de arquivos explica? -> False;
      senão -> True.
    """
    if d_min is None:
        return False
    dt_nome = extrair_data_nome(caminho.stem, ano_minimo)
    if dt_nome is not None:
        return d_min < dt_nome
    dt_fs = metadados.data_filesystem(caminho, ano_minimo)
    if dt_fs is not None and d_min == dt_fs:
        return False
    return True


def calcular_sufixo_pasta(caminho: Path, d_min, cfg: Config, tamanho: int | None) -> str | None:
    """Sufixo de pasta completo do autosufixo (comportamento das versões antigas).

    Ordem de precedência (a primeira regra que casar vence):

    1. Extensão: ``videos``, ``audios``, ``office``, ``outros_tipos``.
    2. Nome: ``screen_capture``, ``social_media``, ``instant_messages``.
    3. Fonte da data: ``metadados`` (restaurado do histórico do projeto).
    4. Tamanho: ``low_resolution``.

    Devolve None quando nenhuma regra casa (pasta só com a data).
    """
    # Sem low_resolution aqui: ele é a ÚLTIMA regra, depois de -metadados
    # (na versão original, low_resolution só entrava se nada mais casasse).
    sufixo = metadados.classificar_sufixo(caminho, tamanho=tamanho, min_size_low_res=0)
    if sufixo:
        return sufixo
    if _data_veio_de_metadados(caminho, d_min, cfg.ano_minimo):
        return SUFIXO_METADADOS
    if tamanho is not None and cfg.min_size_low_res > 0 and tamanho < cfg.min_size_low_res:
        return "low_resolution"
    return None


def proximo_livre(alvo: Path, ocupados: set[Path] | None = None) -> Path:
    """Devolve um nome livre acrescentando _2, _3, ... quando o alvo já existe.

    ``ocupados`` (opcional) é o conjunto de alvos já planejados na execução
    atual: no dry-run nada é gravado no disco, então é ele que faz a
    simulação deduplicar como a execução aplicada faria.
    """
    contador = 2
    while alvo.exists() or (ocupados is not None and alvo in ocupados):
        alvo = alvo.with_name(f"{alvo.stem}_{contador}{alvo.suffix}")
        contador += 1
    return alvo


def _decidir_novo_nome(caminho: Path, tipo: str, d_min, d_max, gps,
                       cfg: Config, contexto, cache_titulos, cache_gps,
                       sha: str | None = None) -> str:
    """Define o nome alvo de uma MÍDIA (título por IA + cidade + hash).

    Retorna o nome pronto ou None quando não há data (o chamador decide
    se mantém o nome original e manda para sem_data).
    """
    if d_min is None:
        return None
    titulo = ia.obter_titulo(caminho, tipo, contexto["ia"], cache_titulos,
                             contexto["cache_titulos_path"], cfg.frames, sha=sha)
    cidade = (geolocalizacao.cidade_ou_coordenadas(gps[0], gps[1], cache_gps,
                                                   contexto["cache_gps_path"])
              if gps else "sem_gps")
    # Hash curto do conteúdo: identifica o arquivo e evita sobrescrita
    # de arquivos diferentes tirados no mesmo segundo. Reaproveita o
    # SHA-256 já calculado para o cache: uma leitura por arquivo, não duas.
    hash6 = hash_curto_6(caminho, digest=sha)
    # Sem título novo (IA desativada ou indisponível), o nome alvo perderia o
    # título que uma execução anterior já gravou no nome. Nesse caso o nome
    # original carrega MAIS informação: mantemos ele.
    if not titulo and preservar_nome_original(caminho.name, d_min, d_max, cidade, hash6):
        logging.info("TÍTULO PRESERVADO (nome original mantido): %s", caminho.name)
        return caminho.name
    novo_nome = montar_nome_midia(d_min, d_max, cidade,
                                  hash6=hash6, titulo=titulo, extensao=caminho.suffix)
    if novo_nome is None:
        logging.warning("Nome alvo muito longo (%s); mantendo nome original.",
                        caminho.name)
        novo_nome = caminho.name
    return novo_nome


def processar_arquivo(caminho: Path, cfg: Config, contexto, cache_titulos, cache_gps, estats: Estatisticas):
    """Processa UM arquivo: define nome/pasta alvo e copia ou move.

    Ordem interna:

    1. Obtém datas/GPS (metadados.obter_datas) e sufixo de pasta.
    2. Mídias (foto/vídeo/áudio) com data são renomeadas no formato
       padrão; os demais arquivos mantêm o nome original.
    3. Resolve conflito de nome existente (duplicar/ignorar/sobrescrever).
    4. Executa a ação (copiar/mover), respeitando o dry-run.
    """
    try:
        tamanho = caminho.stat().st_size
    except OSError:
        tamanho = None
    tipo = classificar_tipo_arquivo(caminho)

    d_min, d_max, gps = metadados.obter_datas(caminho, cfg.ano_minimo)
    sufixo = (calcular_sufixo_pasta(caminho, d_min, cfg, tamanho)
              if cfg.gerar_sufixo else None)
    pasta = montar_pasta_destino(cfg.destino, d_min, cfg.folders_mask, sufixo)

    if tipo in TIPOS_MIDIA and cfg.renomear:
        # Uma única leitura do conteúdo serve ao cache de títulos (SHA-256
        # completo) e ao bloco hash6 do nome (mesmo digest, base 36).
        sha = sha256_arquivo(caminho)
        novo_nome = _decidir_novo_nome(caminho, tipo, d_min, d_max, gps, cfg,
                                       contexto, cache_titulos, cache_gps, sha)
    else:
        novo_nome = None
    if novo_nome is None:
        if d_min is None:
            estats.sem_data += 1
            logging.info("SEM DATA (mantendo nome original; pasta sem_data): %s", caminho)
        novo_nome = caminho.name

    alvo = pasta / novo_nome
    if alvo.resolve() == caminho.resolve():
        logging.info("INALTERADO (já está no destino e no formato alvo): %s", caminho)
        return

    # Colisão de nome: vale para o que já existe no disco E para os alvos
    # já planejados nesta execução (no dry-run nada é gravado, então o
    # conjunto dos planejados é o que torna a simulação fiel à aplicação).
    alvos_planejados = contexto["alvos_planejados"]
    if alvo.exists() or alvo in alvos_planejados:
        if cfg.overwrite == "i":
            estats.ignorados += 1
            logging.info("IGNORADO (já existe no destino): %s -> %s", caminho, alvo)
            return
        if cfg.overwrite != "o":
            alvo = proximo_livre(alvo, alvos_planejados)

    acao = "MOVER" if cfg.mover else "COPIAR"
    if cfg.dry_run:
        logging.info("%s (dry-run): %s -> %s", acao, caminho, alvo)
        levar_sidecar_junto(caminho, alvo, cfg)
        alvos_planejados.add(alvo)
        # Conta no mesmo balde da ação real, senão o resumo do dry-run de
        # --mover diria "copiados" e não bateria com a execução aplicada.
        if cfg.mover:
            estats.movidos += 1
        else:
            estats.copiados += 1
        return
    try:
        pasta.mkdir(parents=True, exist_ok=True)
        if cfg.mover:
            # shutil.move no Windows não sobrescreve arquivo existente
            # (os.rename falha): -w o remove o alvo antes de mover.
            if cfg.overwrite == "o" and alvo.exists():
                alvo.unlink()
            shutil.move(str(caminho), str(alvo))
            estats.movidos += 1
        else:
            shutil.copy2(caminho, alvo)
            estats.copiados += 1
        logging.info("%s: %s -> %s", acao, caminho, alvo)
        levar_sidecar_junto(caminho, alvo, cfg)
    except OSError as e:
        estats.erros += 1
        logging.error("ERRO ao %s %s -> %s (%s)",
                      "mover" if cfg.mover else "copiar", caminho, alvo, e)


def _avisar_origem_igual_destino(cfg: Config) -> bool:
    """Avisa quando o destino fica dentro da origem; devolve True se for o caso.

    Copiar para dentro da própria pasta de origem duplica a coleção (e uma
    segunda execução varreria também as cópias). Mover é seguro, mas ainda
    assim vale o aviso, porque as subpastas de data nascem dentro da origem.
    """
    try:
        origem = cfg.origem.resolve()
        destino = cfg.destino.resolve()
    except OSError:
        return False
    if not destino.is_relative_to(origem):
        return False
    logging.warning(
        "ATENÇÃO: a pasta de destino (%s) está DENTRO da pasta de origem (%s). "
        "%s Considere um destino fora da origem.",
        destino, origem,
        "Ao mover, as subpastas de data serão criadas dentro da própria origem."
        if cfg.mover else
        "Ao copiar, a coleção será DUPLICADA e uma nova execução varreria as cópias.",
    )
    return True


def levar_sidecar_junto(origem: Path, alvo: Path, cfg: Config) -> bool:
    """Leva o relatório de classificação junto com a mídia.

    O ``verificar_fotos_videos`` grava um ``.gemini_36_flash.md`` ao lado de
    cada arquivo analisado. Como ele não é mídia, a varredura não o vê — e,
    sem isto, mover a foto deixava a análise órfã na pasta antiga.

    Devolve True se havia um relatório para levar. Falhas são registradas
    mas não interrompem: a mídia já foi para o lugar certo.
    """
    sidecar = origem.with_name(origem.name + EXT_SIDECAR)
    if not sidecar.is_file():
        return False
    destino = alvo.with_name(alvo.name + EXT_SIDECAR)
    if cfg.dry_run:
        logging.info("  + relatório de classificação (dry-run): %s", destino.name)
        return True
    try:
        if cfg.mover:
            # Mesmo caso da mídia: mover não sobrescreve destino existente
            # no Windows. O relatório tem de acompanhar a mídia, então o
            # antigo no destino sai antes.
            if destino.exists():
                destino.unlink()
            shutil.move(str(sidecar), str(destino))
        else:
            shutil.copy2(sidecar, destino)
        logging.info("  + relatório de classificação levado junto: %s", destino.name)
    except OSError as e:
        logging.warning("Relatório de classificação não acompanhou %s (%s). "
                        "A análise segue no lugar antigo: %s", alvo.name, e, sidecar)
    return True


def organizar(cfg: Config) -> Estatisticas:
    """Executa o organizador completo na pasta de origem.

    - Prepara o contexto de IA (se habilitada) e os caches.
    - Processa os arquivos um a um, com log de progresso.
    - Devolve as estatísticas (total, copiados, movidos, ignorados, erros).
    """
    estats = Estatisticas()
    _avisar_origem_igual_destino(cfg)
    arquivos = coletar_arquivos(cfg.origem)
    if cfg.batch > 0:
        arquivos = arquivos[:cfg.batch]
    estats.total = len(arquivos)
    logging.info("Arquivos encontrados para organizar: %d.", estats.total)

    cache_gps_path = cfg.cache_gps_path or str(DIR_RAIZ / "cache_gps_cidades.json")
    contexto = {
        "ia": None,
        "cache_titulos_path": cfg.cache_titulos_path or str(DIR_RAIZ / "cache_sha256_titulos.jsonl"),
        "cache_gps_path": cache_gps_path,
        # Alvos planejados NESTA execução: no dry-run nada é gravado no
        # disco, então é este conjunto que simula a deduplicação (_2, _3).
        "alvos_planejados": set(),
    }
    if cfg.usar_ia:
        contexto["ia"] = ia.criar_contexto_ia(cfg.chave_gemini, cfg.chave_openai)
    # Contagem por execução (o módulo é importado uma vez; sem zerar, uma
    # segunda chamada de organizar() no mesmo processo somaria errado).
    ia.CONTADOR_CHAMADAS.update({"gemini": 0, "openai": 0})
    cache_titulos = ia.carregar_cache_titulos(contexto["cache_titulos_path"])
    cache_gps = geolocalizacao.carregar_cache_gps(contexto["cache_gps_path"])

    for n, caminho in enumerate(arquivos, 1):
        logging.info("")
        logging.info("[%d/%d] Processando: %s", n, estats.total, caminho)
        processar_arquivo(caminho, cfg, contexto, cache_titulos, cache_gps, estats)
    if cfg.usar_ia:
        logging.info("Chamadas de IA nesta execução: Gemini %d | GPT-4o mini %d",
                     ia.CONTADOR_CHAMADAS["gemini"], ia.CONTADOR_CHAMADAS["openai"])
    return estats
