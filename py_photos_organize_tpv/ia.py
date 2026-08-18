#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""Geração de títulos com IA (Gemini / GPT-4o mini) e cache por SHA-256.

Como funciona:

- **Imagens** são analisadas pelo pacote compartilhado
  ``pereiras_common.ia.analisar_foto`` (que devolve título snake_case,
  resumo, nível de legalidade etc.); aqui usamos apenas o título.
- **Vídeos** usam frames extraídos com ffmpeg e chamadas diretas às APIs
  (Gemini primário, GPT-4o mini como fallback).
- Os resultados são cacheados por SHA-256 em ``cache_sha256_titulos.jsonl``
  para não repetir chamadas à API (não gasta créditos duas vezes).

Chaves de API (importante para segurança):

- As chaves ficam em arquivos FORA do repositório, na pasta pessoal do
  usuário: ``$HOME\.chaves_ia\chave_google_gemini.key`` e
  ``$HOME\.chaves_ia\chave_openai_chatgpt.key`` (padrão do pacote
  compartilhado; no Linux/macOS, ``~/.chaves_ia/``). Nunca versionar
  chaves no git.
- Os caminhos podem ser trocados pela linha de comando:
  ``--chave-gemini`` e ``--chave-openai``.

Sem IA (--sem-ia) ou com falha de conectividade, o título fica vazio e o
arquivo é gerado como YYYY_MM_DD_HHhMMmSSs-YYYY_MM_DD_HHhMMmSSs-cidade-hash6.ext.
"""

import base64
import logging
import re
import shutil
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path

from google import genai
from google.genai import types
from openai import OpenAI
from pereiras_common.ia import ErroAnaliseIA, analisar_foto
from pereiras_common.uteis import (
    DIR_CHAVES_PADRAO,
    carregar_cache_jsonl,
    gravar_cache_jsonl,
    ler_chave,
    normalizar_titulo,
    sha256_arquivo,
)

try:
    import imageio_ffmpeg
    FFMPEG_EXE = imageio_ffmpeg.get_ffmpeg_exe()
except Exception:
    # Sem o binário empacotado, tenta o ffmpeg instalado no sistema.
    FFMPEG_EXE = shutil.which("ffmpeg")

# Raiz do projeto (pasta acima do pacote py_photos_organize_tpv).
DIR_RAIZ = Path(__file__).resolve().parent.parent
CACHE_TITULOS_PADRAO = DIR_RAIZ / "cache_sha256_titulos.jsonl"

# Modelos usados para vídeos (as fotos usam os padrões do pereiras_common).
MODELO_GEMINI = "gemini-3.6-flash"
MODELO_OPENAI = "gpt-4o-mini"

# Tamanho máximo dos frames enviados à IA (economia de tokens).
MAX_DIM = 1024
QUALIDADE_JPEG = 85

# Contador de chamadas por provedor (exibido nos logs/resumo).
CONTADOR_CHAMADAS = {"gemini": 0, "openai": 0}

# Pedido enviado às APIs para vídeos: apenas o título.
PROMPT_TITULO = (
    "Resuma o conteúdo da imagem em um título de no máximo 5 palavras, em português. "
    "Responda APENAS com o título: sem pontuação, sem aspas e sem markdown."
)


def carregar_cache_titulos(cache_path=None):
    """Lê o cache de títulos (JSONL) e devolve {sha256: registro}.

    Delegado a ``pereiras_common.uteis.carregar_cache_jsonl`` — a mesma
    implementação usada pelo cache de classificações do verificar_fotos_videos.
    """
    return carregar_cache_jsonl(Path(cache_path) if cache_path else CACHE_TITULOS_PADRAO)


def gravar_cache_titulos(registro, cache_path=None):
    """Anexa um registro ao cache de títulos (append-only, formato JSONL)."""
    gravar_cache_jsonl(registro, Path(cache_path) if cache_path else CACHE_TITULOS_PADRAO)


def criar_client_gemini(chave):
    """Cria o cliente Gemini com timeout estendido (imagens demoram mais)."""
    try:
        return genai.Client(
            api_key=chave,
            http_options=types.HttpOptions(timeout=120000),
        )
    except Exception:
        # SDKs mais antigos podem não aceitar http_options: cria simples.
        return genai.Client(api_key=chave)


def criar_client_openai(chave):
    """Cria o cliente OpenAI (GPT) com timeout de 120 segundos."""
    return OpenAI(api_key=chave, timeout=120.0)


def verificar_gemini(client):
    """Pré-voo do Gemini: uma chamada barata para validar chave/conexão.

    Se falhar, o cliente é considerado indisponível e não será usado.
    """
    try:
        client.models.generate_content(
            model=MODELO_GEMINI, contents="Responda apenas: ok",
            config=types.GenerateContentConfig(max_output_tokens=20),
        )
        # Resposta vazia ainda é sucesso: a API respondeu, então a chave e o
        # modelo estão válidos (o limite baixo de tokens pode zerar o texto).
        return True
    except Exception as e:
        logging.error("Falha no teste pré-voo do Gemini: %s", e)
        return False


def verificar_openai(client):
    """Pré-voo do GPT-4o mini: uma chamada barata para validar chave/conexão."""
    try:
        client.chat.completions.create(
            model=MODELO_OPENAI,
            messages=[{"role": "user", "content": "Responda apenas: ok"}],
            max_tokens=10,
            temperature=0,
        )
        return True
    except Exception as e:
        logging.error("Falha no teste pré-voo do GPT-4o mini: %s", e)
        return False


def criar_contexto_ia(chave_gemini_path=None, chave_openai_path=None):
    r"""Cria o contexto de IA: clientes funcionais + chaves para análise.

    Leitura das chaves:

    - Parâmetros ``chave_gemini_path``/``chave_openai_path`` (vindos da
      linha de comando) têm prioridade.
    - Sem parâmetro, procura na pasta ``$HOME\.chaves_ia\`` um arquivo cujo
      nome cite o provedor — ``chave_google_gemini.key``,
      ``CHAVE_GOOGLE_GEMINI.txt``, ``._CHAVE_GOOGLE_GEMINI.txt`` etc.
    - Os caminhos aceitam ``~``, ``$HOME`` e ``%USERPROFILE%``.

    Retorna um dict com as chaves "gemini" e/ou "openai" (clientes que
    passaram no pré-voo) e "chave_gemini"/"chave_openai" (texto das
    chaves, para a análise de fotos do pacote compartilhado). Retorna
    None se nenhuma IA estiver disponível.
    """
    contexto = {}
    # Sem --chave-gemini, procura na pasta padrão aceitando variações de nome
    # (chave_google_gemini.key, CHAVE_GOOGLE_GEMINI.txt, ._CHAVE_...txt).
    chave_gemini = ler_chave(chave_gemini_path or DIR_CHAVES_PADRAO, tipo="gemini")
    if chave_gemini:
        try:
            cliente = criar_client_gemini(chave_gemini)
            if verificar_gemini(cliente):
                contexto["gemini"] = cliente
                contexto["chave_gemini"] = chave_gemini
                logging.info("IA Gemini disponível (%s).", MODELO_GEMINI)
            else:
                logging.warning("IA Gemini indisponível (pré-voo falhou).")
        except Exception as e:
            logging.warning("Não foi possível criar o cliente Gemini: %s", e)
    chave_openai = ler_chave(chave_openai_path or DIR_CHAVES_PADRAO, tipo="openai")
    if chave_openai:
        try:
            cliente = criar_client_openai(chave_openai)
            if verificar_openai(cliente):
                contexto["openai"] = cliente
                contexto["chave_openai"] = chave_openai
                logging.info("IA GPT-4o mini disponível (%s).", MODELO_OPENAI)
            else:
                logging.warning("IA GPT-4o mini indisponível (pré-voo falhou).")
        except Exception as e:
            logging.warning("Não foi possível criar o cliente GPT-4o mini: %s", e)
    if not contexto:
        logging.warning("Nenhuma IA disponível; arquivos serão gerados sem o bloco de título "
                        "({data1}-{data2}-{cidade}-{hash6}{ext}).")
        return None
    return contexto


def extrair_frames_video(caminho, n_frames=5):
    """Extrai frames em intervalos regulares do vídeo (ffmpeg).

    - Lê a duração do vídeo do stderr do ffmpeg.
    - Escolhe momentos espaçados uniformemente ao longo do vídeo.
    - Extrai 1 frame por momento, redimensionado para MAX_DIM pixels.

    Retorna uma lista de bytes JPEG (vazia em caso de falha).
    """
    if not FFMPEG_EXE:
        return []
    try:
        # 1ª passada: só para descobrir a duração (impressa no stderr).
        r = subprocess.run(
            [FFMPEG_EXE, "-hide_banner", "-i", str(caminho), "-f", "null", "-"],
            capture_output=True, text=True, timeout=180,
        )
        m = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", r.stderr or "")
        duracao = None
        if m:
            duracao = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))
    except (OSError, subprocess.TimeoutExpired):
        return []
    # Vídeos muito curtos: usa um único momento (0,1 s).
    if not duracao or duracao <= 1.0:
        momentos = [0.1]
    else:
        n = max(1, min(n_frames, int(duracao)))
        momentos = [min(max(duracao * (i + 0.5) / n, 0.05), duracao - 0.05) for i in range(n)]
    # 2ª passada: extrai cada frame para um arquivo temporário.
    frames = []
    with tempfile.TemporaryDirectory(prefix="organize_frames_") as tmp:
        for i, t in enumerate(momentos):
            saida = Path(tmp) / f"frame_{i:02d}.jpg"
            cmd = [
                FFMPEG_EXE, "-y", "-loglevel", "error",
                "-ss", f"{t:.3f}", "-i", str(caminho),
                "-frames:v", "1",
                "-vf", f"scale={MAX_DIM}:{MAX_DIM}:force_original_aspect_ratio=decrease",
                "-q:v", "3", str(saida),
            ]
            try:
                r = subprocess.run(cmd, capture_output=True, timeout=180)
            except (subprocess.TimeoutExpired, OSError):
                continue
            if r.returncode == 0 and saida.exists() and saida.stat().st_size > 0:
                frames.append(saida.read_bytes())
    return frames


def gerar_titulo_gemini(client, frames):
    """Pede um título ao Gemini para os frames do vídeo."""
    parts = [types.Part.from_text(text=PROMPT_TITULO)]
    for f in frames:
        parts.append(types.Part.from_bytes(data=f, mime_type="image/jpeg"))
    resp = client.models.generate_content(
        model=MODELO_GEMINI, contents=parts,
        config=types.GenerateContentConfig(temperature=0.2, max_output_tokens=60),
    )
    CONTADOR_CHAMADAS["gemini"] += 1
    return normalizar_titulo(resp.text or "")


def gerar_titulo_openai(client, frames):
    """Pede um título ao GPT-4o mini para os frames do vídeo."""
    conteudo = [{"type": "text", "text": PROMPT_TITULO}]
    for f in frames:
        conteudo.append({
            "type": "image_url",
            "image_url": {"url": f"data:image/jpeg;base64,{base64.b64encode(f).decode('ascii')}"},
        })
    resp = client.chat.completions.create(
        model=MODELO_OPENAI,
        messages=[{"role": "user", "content": conteudo}],
        temperature=0.2,
        max_tokens=60,
    )
    CONTADOR_CHAMADAS["openai"] += 1
    titulo = ""
    if resp.choices:
        titulo = getattr(resp.choices[0].message, "content", "") or ""
    return normalizar_titulo(titulo)


def _gerar_titulo_video_com_fallback(contexto, frames, preferencia):
    """Tenta gerar o título do vídeo com fallback cruzado entre as IAs.

    - preferencia = "gemini" tenta Gemini primeiro; caso contrário, OpenAI.
    - Se o modelo preferido falhar, tenta o outro.
    - Se todos falharem, lança RuntimeError (o chamador decide o que fazer).
    """
    pares = [
        (contexto.get("openai"), "GPT-4o mini", gerar_titulo_openai),
        (contexto.get("gemini"), "Gemini", gerar_titulo_gemini),
    ]
    if preferencia == "gemini":
        pares.reverse()
    ultimo_erro = None
    for cliente, nome, funcao in pares:
        if cliente is None:
            continue
        try:
            titulo = funcao(cliente, frames)
            if titulo:
                logging.debug("Título gerado pelo %s.", nome)
                return titulo
        except Exception as e:
            ultimo_erro = e
            logging.warning("Falha ao gerar título com %s: %s", nome, e)
    if ultimo_erro:
        raise RuntimeError("nenhuma IA conseguiu gerar o título") from ultimo_erro
    return ""


def _titulo_imagem_compartilhado(contexto, caminho):
    """Título de uma IMAGEM via pereiras_common.ia.analisar_foto.

    Preferência: OpenAI primeiro, Gemini como fallback. Retorna "" se
    nenhuma IA estiver disponível ou se as análises falharem.
    """
    titulo = ""
    chave_openai = contexto.get("chave_openai")
    chave_gemini = contexto.get("chave_gemini")
    if chave_openai:
        try:
            titulo = analisar_foto(chave_openai, "openai", caminho).titulo
            logging.debug("Título da imagem gerado pelo GPT-4o mini.")
        except ErroAnaliseIA as e:
            logging.warning("GPT-4o mini falhou na imagem: %s", e)
    if not titulo and chave_gemini:
        try:
            titulo = analisar_foto(chave_gemini, "gemini", caminho).titulo
            logging.debug("Título da imagem gerado pelo Gemini.")
        except ErroAnaliseIA as e:
            logging.warning("Gemini falhou na imagem: %s", e)
    return titulo


def obter_titulo(caminho, tipo, contexto, cache, cache_path=None, n_frames=5,
                 sha=None):
    """Título em snake_case gerado por IA (com cache SHA-256).

    - Imagens: análise pelo pacote compartilhado (OpenAI -> Gemini).
    - Vídeos: frames extraídos por ffmpeg (Gemini -> OpenAI).
    - Cache: arquivos idênticos (SHA-256) reutilizam o título salvo.
    - ``sha``: SHA-256 já calculado pelo chamador (opcional).

    Retorna "" quando a IA está desativada (--sem-ia) ou indisponível
    (sem chave, sem conectividade, falha nas chamadas). Nesse caso o
    arquivo é gerado sem o bloco {titulo}: {data1}-{data2}-{cidade}-{hash6}{ext}.

    Só títulos gerados com sucesso entram no cache; falhas não são
    cacheadas para permitir novas tentativas em execuções futuras.
    """
    if not contexto:
        return ""
    # ``sha`` já calculado pelo chamador evita uma segunda leitura completa
    # do arquivo (o organizador precisa do mesmo hash para o nome).
    if sha is None:
        sha = sha256_arquivo(caminho)
    if sha and sha in cache and cache[sha].get("titulo"):
        return cache[sha]["titulo"]
    titulo = ""
    if sha:
        try:
            if tipo == "imagem":
                titulo = _titulo_imagem_compartilhado(contexto, caminho)
            elif tipo == "video":
                frames = extrair_frames_video(caminho, n_frames)
                if frames:
                    titulo = _gerar_titulo_video_com_fallback(contexto, frames, preferencia="gemini")
        except Exception as e:
            logging.warning("IA indisponível para %s (%s); arquivo será gerado sem título.",
                            caminho.name, e)
    if not titulo:
        return ""
    if sha:
        cache[sha] = {"sha256": sha, "titulo": titulo,
                      "data": datetime.now().isoformat(timespec="seconds")}
        gravar_cache_titulos(cache[sha], cache_path)
    return titulo
