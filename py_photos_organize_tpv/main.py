#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Interface de linha de comando do pyPhotosOrganizeTPV.

Organiza fotos, vídeos e outros formatos em subpastas por data, gerando
arquivos no formato {data1}-{data2}-{cidade}-{titulo}{ext}.

Exemplos:
  uv run python -m py_photos_organize_tpv -o D:\\fotos -d E:\\organizado
  uv run python -m py_photos_organize_tpv -o D:\\fotos -d E:\\organizado --dry-run
  uv run python -m py_photos_organize_tpv -o D:\\fotos -d E:\\organizado --sem-ia
  uv run python -m py_photos_organize_tpv -o D:\\fotos -d E:\\organizado --mover -q 100

Resiliência: se a IA estiver desativada (--sem-ia) ou indisponível
(sem chave ou sem conectividade), os arquivos são gerados sem o bloco
{titulo}: {data1}-{data2}-{cidade}{ext}.
"""

import argparse
import logging
import sys
from datetime import datetime
from pathlib import Path

import coloredlogs

try:
    from . import metadados
    from .organizador import Config, organizar
except ImportError:
    import metadados
    from organizador import Config, organizar

DIR_RAIZ = Path(__file__).resolve().parent.parent
DIR_LOGS = DIR_RAIZ / "logs"


def criar_parser():
    ap = argparse.ArgumentParser(
        description="Organiza fotos/vídeos por data (EXIF/metadados), gerando arquivos "
                    "no formato {data1}-{data2}-{cidade}-{titulo}{ext}.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("-o", "--files-orign", type=str, default="d:\\",
                    help="pasta de origem a percorrer (padrão: d:\\)")
    ap.add_argument("-d", "--files-destination", type=str, default="E:\\TMP-fotos",
                    help="pasta de destino (padrão: E:\\TMP-fotos)")
    ap.add_argument("-f", "--folders", type=str, default="%Y_%m",
                    help="máscara strftime das subpastas de data (padrão: %%Y_%%m)")
    ap.add_argument("-w", "--overwrite", choices=["d", "i", "o"], default="d",
                    help="se o arquivo já existe no destino: d=duplicar, i=ignorar, o=sobrescrever")
    ap.add_argument("-q", "--batch-quantity-files", type=int, default=0,
                    help="processa no máximo N arquivos (0 = todos)")
    ap.add_argument("-y", "--min-year-discart-date", type=int, default=1980,
                    help="ignora datas anteriores a este ano")
    ap.add_argument("-s", "--min-size-escape-low-resolution", type=int, default=100000,
                    help="arquivos menores que este tamanho (bytes) ganham sufixo low_resolution")
    ap.add_argument("-g", "--generate-folder-sufix", action=argparse.BooleanOptionalAction,
                    default=True, help="gera sufixo de pasta por origem (videos, social_media, ...)")
    ap.add_argument("-n", "--rename-file", action=argparse.BooleanOptionalAction,
                    default=True, help="renomeia o arquivo para o formato alvo")
    ap.add_argument("-l", "--timestamp-log", action=argparse.BooleanOptionalAction,
                    default=True, help="nome do arquivo de log com timestamp")
    ap.add_argument("--sem-ia", action="store_true",
                    help="não usa APIs de IA (sem consumo de tokens/créditos); "
                         "arquivos gerados sem o bloco de título")
    ap.add_argument("--chave-gemini", type=str, default=None,
                    help="arquivo com a chave da API Gemini (padrão: ._SECRETS/._CHAVE_GEMINI.key)")
    ap.add_argument("--chave-openai", type=str, default=None,
                    help="arquivo com a chave da API OpenAI (padrão: ._SECRETS/._CHAVE_OPENAI_CHATGPT.key)")
    ap.add_argument("--dry-run", action="store_true",
                    help="apenas mostra o que seria feito, sem alterar nada")
    ap.add_argument("--mover", action="store_true",
                    help="move os arquivos em vez de copiá-los")
    ap.add_argument("--frames", type=int, default=5,
                    help="frames extraídos por vídeo para a IA")
    return ap


def main(argv=None):
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

    origem = Path(args.files_orign)
    destino = Path(args.files_destination)
    if not origem.is_dir():
        sys.exit(f"ERRO: pasta de origem não encontrada: {origem}")
    if args.dry_run:
        logging.info("MODO DRY-RUN: nada será alterado.")

    metadados.registrar_heif()

    cfg = Config(
        origem=origem,
        destino=destino,
        folders_mask=args.folders,
        overwrite=args.overwrite,
        batch=args.batch_quantity_files,
        ano_minimo=args.min_year_discart_date,
        min_size_low_res=args.min_size_escape_low_resolution,
        gerar_sufixo=args.generate_folder_sufix,
        renomear=args.rename_file,
        usar_ia=not args.sem_ia,
        dry_run=args.dry_run,
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
                 "DRY-RUN" if cfg.dry_run else "APLICADO",
                 estats.total, estats.copiados, estats.movidos,
                 estats.ignorados, estats.sem_data, estats.erros)
    logging.info("Log completo: %s", arquivo_log)


if __name__ == "__main__":
    main()
