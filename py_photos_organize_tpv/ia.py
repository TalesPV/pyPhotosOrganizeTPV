#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Geração de títulos com IA (Gemini / GPT-4o mini) e cache por SHA-256.

As chaves de API ficam em ._SECRETS/ (._CHAVE_GEMINI.key e
._CHAVE_OPENAI_CHATGPT.key). O título gerado compõe o bloco {titulo} do
formato alvo de nome:
    {data1}-{data2}-{cidade}-{titulo}{ext}

Sem IA (--sem-ia) ou com falha de conectividade, o título fica vazio e o
arquivo é gerado como {data1}-{data2}-{cidade}{ext}.

Imagens usam GPT-4o mini como modelo primário e vídeos usam Gemini,
sempre com fallback cruzado. Resultados são cacheados por SHA-256 para
não repetir chamadas à API (cache_sha256_titulos.jsonl).
"""

import base64
import hashlib
import json
import logging
import shutil
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path

from google import genai
from google.genai import types
from openai import OpenAI
from PIL import Image

try:
    from .nomeacao import para_snake_case
except ImportError:
    from nomeacao import para_snake_case

DIR_RAIZ = Path(__file__).resolve().parent.parent
DIR_SECRETS = DIR_RAIZ / "._SECRETS"
CHAVE_GEMINI_PADRAO = DIR_SECRETS / "._CHAVE_GEMINI.key"
CHAVE_OPENAI_PADRAO = DIR_SECRETS / "._CHAVE_OPENAI_CHATGPT.key"
CACHE_TITULOS_PADRAO = DIR_RAIZ / "cache_sha256_titulos.jsonl"

MODELO_GEMINI = "gemini-3.6-flash"
MODELO_OPENAI = "gpt-4o-mini"
MAX_DIM = 1024
QUALIDADE_JPEG = 85
CONTADOR_CHAMADAS = {"gemini": 0, "openai": 0}

PROMPT_TITULO = (
    "Resuma o conteúdo da imagem em um título de no máximo 5 palavras, em português. "
    "Responda APENAS com o título: sem pontuação, sem aspas e sem markdown."
)

try:
    import imageio_ffmpeg
    FFMPEG_EXE = imageio_ffmpeg.get_ffmpeg_exe()
except Exception:
    FFMPEG_EXE = shutil.which("ffmpeg")


def sha256_arquivo(caminho):
    h = hashlib.sha256()
    try:
        with open(caminho, "rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                h.update(chunk)
    except OSError:
        return None
    return h.hexdigest()


def carregar_cache_titulos(cache_path=None):
    path = Path(cache_path) if cache_path else CACHE_TITULOS_PADRAO
    cache = {}
    if not path.exists():
        return cache
    try:
        with open(path, encoding="utf-8") as f:
            for linha in f:
                linha = linha.strip()
                if not linha:
                    continue
                try:
                    reg = json.loads(linha)
                except json.JSONDecodeError:
                    continue
                if reg.get("sha256"):
                    cache[reg["sha256"]] = reg
    except OSError:
        pass
    return cache


def gravar_cache_titulos(registro, cache_path=None):
    path = Path(cache_path) if cache_path else CACHE_TITULOS_PADRAO
    try:
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(registro, ensure_ascii=False) + "\n")
    except OSError:
        pass


def carregar_chave(caminho):
    p = Path(caminho)
    if not p.is_file():
        return None
    chave = p.read_text(encoding="utf-8").strip()
    return chave if len(chave) >= 10 else None


def criar_client_gemini(chave):
    try:
        return genai.Client(
            api_key=chave,
            http_options=types.HttpOptions(timeout=120000),
        )
    except Exception:
        return genai.Client(api_key=chave)


def criar_client_openai(chave):
    return OpenAI(api_key=chave, timeout=120.0)


def verificar_gemini(client):
    try:
        r = client.models.generate_content(
            model=MODELO_GEMINI, contents="Responda apenas: ok",
            config=types.GenerateContentConfig(max_output_tokens=20),
        )
        return True if (r.text or "") else True
    except Exception as e:
        logging.error("Falha no teste pré-voo do Gemini: %s", e)
        return False


def verificar_openai(client):
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
    """Cria os clientes de IA disponíveis (pré-voo de cada um).

    Retorna um dict com os clientes funcionais (chaves "gemini" e/ou "openai")
    ou None se nenhuma IA estiver disponível.
    """
    contexto = {}
    chave_gemini = carregar_chave(chave_gemini_path or CHAVE_GEMINI_PADRAO)
    if chave_gemini:
        try:
            cliente = criar_client_gemini(chave_gemini)
            if verificar_gemini(cliente):
                contexto["gemini"] = cliente
                logging.info("IA Gemini disponível (%s).", MODELO_GEMINI)
            else:
                logging.warning("IA Gemini indisponível (pré-voo falhou).")
        except Exception as e:
            logging.warning("Não foi possível criar o cliente Gemini: %s", e)
    chave_openai = carregar_chave(chave_openai_path or CHAVE_OPENAI_PADRAO)
    if chave_openai:
        try:
            cliente = criar_client_openai(chave_openai)
            if verificar_openai(cliente):
                contexto["openai"] = cliente
                logging.info("IA GPT-4o mini disponível (%s).", MODELO_OPENAI)
            else:
                logging.warning("IA GPT-4o mini indisponível (pré-voo falhou).")
        except Exception as e:
            logging.warning("Não foi possível criar o cliente GPT-4o mini: %s", e)
    if not contexto:
        logging.warning("Nenhuma IA disponível; arquivos serão gerados sem o bloco de título "
                        "({data1}-{data2}-{cidade}{ext}).")
        return None
    return contexto


def normalizar_titulo(titulo):
    """Limpa a resposta da IA e limita a 5 palavras em snake_case.

    Retorna "" quando a resposta não produzir um título válido.
    """
    t = str(titulo or "").strip().strip('"`*#')
    palavras = t.split()
    if len(palavras) > 5:
        t = " ".join(palavras[:5])
    t = para_snake_case(t)
    return t if t != "sem_nome" else ""


def preparar_imagem(caminho):
    try:
        img = Image.open(caminho)
        img = img.convert("RGB")
        img.thumbnail((MAX_DIM, MAX_DIM), Image.Resampling.LANCZOS)
        buf = tempfile.SpooledTemporaryFile(max_size=8 * 1024 * 1024)
        img.save(buf, format="JPEG", quality=QUALIDADE_JPEG)
        buf.seek(0)
        return buf.read()
    except Exception as e:
        raise RuntimeError(f"não foi possível ler a imagem ({e})") from e


def extrair_frames_video(caminho, n_frames=5):
    """Extrai frames em intervalos regulares do vídeo (ffmpeg)."""
    if not FFMPEG_EXE:
        return []
    try:
        r = subprocess.run(
            [FFMPEG_EXE, "-hide_banner", "-i", str(caminho), "-f", "null", "-"],
            capture_output=True, text=True, timeout=180,
        )
        import re
        m = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", r.stderr or "")
        duracao = None
        if m:
            duracao = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))
    except (OSError, subprocess.TimeoutExpired):
        return []
    if not duracao or duracao <= 1.0:
        momentos = [0.1]
    else:
        n = max(1, min(n_frames, int(duracao)))
        momentos = [min(max(duracao * (i + 0.5) / n, 0.05), duracao - 0.05) for i in range(n)]
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


def _gerar_titulo_com_fallback(contexto, frames, preferencia):
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


def obter_titulo(caminho, tipo, contexto, cache, cache_path=None, n_frames=5):
    """Título em snake_case gerado por IA (com cache SHA-256).

    Retorna "" quando a IA está desativada (--sem-ia) ou indisponível
    (sem chave, sem conectividade, falha nas chamadas). Nesse caso o
    arquivo é gerado sem o bloco {titulo}: {data1}-{data2}-{cidade}{ext}.

    Só títulos gerados com sucesso entram no cache; falhas não são
    cacheadas para permitir novas tentativas em execuções futuras.
    """
    if not contexto:
        return ""
    sha = sha256_arquivo(caminho)
    if sha and sha in cache and cache[sha].get("titulo"):
        return cache[sha]["titulo"]
    titulo = ""
    if sha:
        try:
            if tipo == "imagem":
                frames = [preparar_imagem(caminho)]
                titulo = _gerar_titulo_com_fallback(contexto, frames, preferencia="openai")
            elif tipo == "video":
                frames = extrair_frames_video(caminho, n_frames)
                if frames:
                    titulo = _gerar_titulo_com_fallback(contexto, frames, preferencia="gemini")
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
