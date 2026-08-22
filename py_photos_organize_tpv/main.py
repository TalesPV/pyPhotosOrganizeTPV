#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""Interface de linha de comando do pyPhotosOrganizeTPV.

Organiza fotos, vídeos e áudios em subpastas por data, gerando arquivos
no formato padrão de mídia:

    YYYY_MM_DD_HHhMMmSSs-YYYY_MM_DD_HHhMMmSSs-cidade-hash6-titulo.ext

Arquivos que não são mídia (office, PDFs etc.) mantêm o nome original.

Exemplos:
  uv run python -m py_photos_organize_tpv -o D:\\fotos -d E:\\organizado
  uv run python -m py_photos_organize_tpv -o D:\\fotos -d E:\\organizado --dry-run
  uv run python -m py_photos_organize_tpv -o D:\\fotos -d E:\\organizado --sem-ia
  uv run python -m py_photos_organize_tpv -o D:\\fotos -d E:\\organizado --mover -q 100
  uv run python -m py_photos_organize_tpv -o D:\\fotos -d E:\\organizado --com-autosufixo-pastas

IA é opt-in: sem --com-ia nenhuma API é chamada. Nesse caso (ou se a IA
estiver indisponível por falta de chave ou de rede), os arquivos são
gerados sem o bloco {titulo}:
YYYY_MM_DD_HHhMMmSSs-YYYY_MM_DD_HHhMMmSSs-cidade-hash6.ext.
Um título já gravado no nome NÃO é perdido (ver preservar_nome_original).
"""

import argparse
import logging
import sys
from datetime import datetime
from pathlib import Path

import coloredlogs
from pereiras_common import metadados
from pereiras_common.nomeacao import ANO_MINIMO_PADRAO
from pereiras_common.uteis import expandir_caminho

from .organizador import Config, organizar

DIR_RAIZ = Path(__file__).resolve().parent.parent
DIR_LOGS = DIR_RAIZ / "logs"


def criar_parser():
    """Cria e configura o parser de argumentos da linha de comando.

    Cada opção do CLI vira um campo da Config (ver organizador.Config).
    Os padrões aqui definidos valem quando o usuário não informa nada.
    """
    ap = argparse.ArgumentParser(
        description="Organiza fotos/vídeos/áudios por data (EXIF/metadados), gerando "
                    "arquivos no formato YYYY_MM_DD_HHhMMmSSs-YYYY_MM_DD_HHhMMmSSs-"
                    "cidade-hash6-titulo.ext.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("-o", "--files-orign", type=str, required=True,
                    help="pasta de origem a percorrer (recursivo) — obrigatório")
    ap.add_argument("-d", "--files-destination", type=str, required=True,
                    help="pasta de destino — obrigatório")
    ap.add_argument("-f", "--folders", type=str, default="%Y_%m",
                    help="máscara strftime das subpastas de data (padrão: %%Y_%%m)")
    ap.add_argument("-w", "--overwrite", choices=["d", "i", "o"], default="d",
                    help="se o arquivo já existe no destino: d=duplicar, i=ignorar, o=sobrescrever")
    ap.add_argument("-q", "--batch-quantity-files", type=int, default=0,
                    help="processa no máximo N arquivos (0 = todos)")
    ap.add_argument("-y", "--min-year-discart-date", type=int,
                    default=ANO_MINIMO_PADRAO,
                    help=f"ignora datas anteriores a este ano "
                         f"(padrão: {ANO_MINIMO_PADRAO}, o mesmo dos outros programas)")
    ap.add_argument("-s", "--min-size-escape-low-resolution", type=int, default=100000,
                    help="arquivos menores que este tamanho (bytes) ganham sufixo low_resolution")
    # Sufixos automáticos de pasta são opt-in: sem a flag, as pastas são
    # apenas a máscara de data. -g continua aceito (legado) para não quebrar
    # scripts antigos; equivale a --com-autosufixo-pastas.
    ap.add_argument("--com-autosufixo-pastas", action="store_true",
                    help="ativa os sufixos automáticos de pasta: office, videos, audios, "
                         "outros_tipos, screen_capture, social_media, instant_messages, "
                         "metadados (fonte da data) e low_resolution (tamanho)")
    ap.add_argument("-g", "--generate-folder-sufix", action=argparse.BooleanOptionalAction,
                    default=False,
                    help="(legado) o mesmo que --com-autosufixo-pastas; "
                         "aceita --no-generate-folder-sufix")
    ap.add_argument("-n", "--rename-file", action=argparse.BooleanOptionalAction,
                    default=True, help="renomeia o arquivo para o formato alvo")
    ap.add_argument("-l", "--timestamp-log", action=argparse.BooleanOptionalAction,
                    default=True, help="nome do arquivo de log com timestamp")
    # A IA custa dinheiro por arquivo, então é opt-in: sem --com-ia, não roda.
    # --sem-ia continua aceito (agora redundante) para não quebrar scripts
    # antigos; usar os dois juntos é ambíguo e o argparse recusa.
    grupo_ia = ap.add_mutually_exclusive_group()
    grupo_ia.add_argument("--com-ia", action="store_true",
                          help="gera o bloco de título com IA (consome tokens e "
                               "créditos). Sem esta opção, nenhuma API é chamada")
    grupo_ia.add_argument("--sem-ia", action="store_true",
                          help="explicita que não se deve usar IA (já é o padrão)")
    ap.add_argument("--chave-gemini", type=str, default=None,
                    help="arquivo com a chave da API Gemini "
                         r"(padrão: $HOME\.chaves_ia\chave_google_gemini.key)")
    ap.add_argument("--chave-openai", type=str, default=None,
                    help="arquivo com a chave da API OpenAI "
                         r"(padrão: $HOME\.chaves_ia\chave_openai_chatgpt.key)")
    ap.add_argument("--aplicar", action="store_true",
                    help="executa as alterações (padrão: apenas simula, "
                         "sem alterar nada no disco)")
    # Mantido por compatibilidade com scripts e anotações antigas: simular
    # já é o padrão, então a opção existe mas não muda mais nada.
    ap.add_argument("--dry-run", action="store_true",
                    help=argparse.SUPPRESS)
    ap.add_argument("--mover", action="store_true",
                    help="move os arquivos em vez de copiá-los")
    ap.add_argument("--frames", type=int, default=5,
                    help="frames extraídos por vídeo para a IA")
    return ap


def main(argv=None):
    """Ponto de entrada do CLI: parseia argumentos e executa o organizador.

    Passos: configurar log, validar a pasta de origem, registrar o opener
    HEIC (fotos de iPhone), montar a Config e chamar organizar().
    """
    ap = criar_parser()
    args = ap.parse_args(argv)

    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    DIR_LOGS.mkdir(parents=True, exist_ok=True)
    sufixo_log = datetime.now().strftime("%Y%m%d_%H%M%S") if args.timestamp_log else "atual"
    arquivo_log = DIR_LOGS / f"log_py_photos_organize_tpv_{sufixo_log}.log"
    logging.basicConfig(
        level=logging.INFO,
        handlers=[logging.FileHandler(arquivo_log, encoding="utf-8")],
    )
    coloredlogs.install(level="INFO", fmt="%(asctime)s [%(levelname)s] %(message)s")

    # expandir_caminho aceita ~, $HOME e %USERPROFILE% (o PowerShell não
    # expande $HOME quando o argumento vem entre aspas simples).
    origem = expandir_caminho(args.files_orign)
    destino = expandir_caminho(args.files_destination)
    if not origem.is_dir():
        sys.exit(f"ERRO: pasta de origem não encontrada: {origem}")
    if not args.aplicar:
        logging.info("MODO SIMULAÇÃO: nada será alterado. Use --aplicar para executar.")
    if not args.com_ia:
        logging.info("SEM IA (padrão): nenhuma API será chamada e os arquivos sairão "
                     "sem o bloco de título. Use --com-ia para gerar títulos.")

    metadados.registrar_heif()

    cfg = Config(
        origem=origem,
        destino=destino,
        folders_mask=args.folders,
        overwrite=args.overwrite,
        batch=args.batch_quantity_files,
        ano_minimo=args.min_year_discart_date,
        min_size_low_res=args.min_size_escape_low_resolution,
        # Qualquer uma das formas liga os sufixos automáticos de pasta:
        # a canônica (--com-autosufixo-pastas) ou a legada (-g).
        gerar_sufixo=args.generate_folder_sufix or args.com_autosufixo_pastas,
        renomear=args.rename_file,
        usar_ia=args.com_ia,
        dry_run=not args.aplicar,
        mover=args.mover,
        frames=args.frames,
        chave_gemini=args.chave_gemini,
        chave_openai=args.chave_openai,
    )

    try:
        estats = organizar(cfg)
    except KeyboardInterrupt:
        logging.warning("Interrompido pelo usuário (Ctrl+C).")
        sys.exit(0)

    logging.info("=" * 60)
    logging.info("RESUMO (%s): %d total | %d copiados | %d movidos | %d ignorados | "
                 "%d sem data | %d erros",
                 "SIMULAÇÃO" if cfg.dry_run else "APLICADO",
                 estats.total, estats.copiados, estats.movidos,
                 estats.ignorados, estats.sem_data, estats.erros)
    logging.info("Log completo: %s", arquivo_log)


if __name__ == "__main__":
    main()
