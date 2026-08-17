#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Extração de datas e GPS de metadados (imagens e vídeos) e do sistema de arquivos.

Fontes de metadados por tipo de arquivo:
- Imagens: EXIF (Pillow), XMP (GPS e datas), texto PNG (tEXt/iTXt: "Creation Time",
  "date:create" etc.). Fallback opcional: binário exiftool, se instalado.
- Vídeos: ffmpeg (creation_time e location em ISO 6709 / ©xyz do QuickTime).
  Fallback opcional: binário exiftool, se instalado.
- Sistema de arquivos: data de criação/modificação (última alternativa).
"""

import json
import logging
import re
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

from PIL import Image

try:
    from .nomeacao import dentro_do_periodo, montar_dt, parsear_data_exif
except ImportError:
    from nomeacao import dentro_do_periodo, montar_dt, parsear_data_exif

EXTS_IMAGEM = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".tif", ".tiff", ".heic", ".heif"}
EXTS_VIDEO = {".mp4", ".avi", ".mov", ".mkv", ".wmv", ".webm", ".mpg", ".mpeg", ".3gp", ".m4v", ".flv", ".ts"}
EXTS_AUDIO = {".amr", ".aac", ".mp3", ".opus", ".ogg"}
EXTS_OFFICE = {".doc", ".docx", ".xls", ".xlsx", ".ods", ".rtf"}
EXTS_OUTROS = {".pdf", ".txt", ".url", ".lnk", ".zip", ".htm", ".html", ".js"}
ALL_EXTENSIONS = EXTS_IMAGEM | EXTS_VIDEO | EXTS_AUDIO | EXTS_OFFICE | EXTS_OUTROS

try:
    import imageio_ffmpeg
    FFMPEG_EXE = imageio_ffmpeg.get_ffmpeg_exe()
except Exception:
    FFMPEG_EXE = shutil.which("ffmpeg")

EXIFTOOL_EXE = shutil.which("exiftool")

RE_CREATION_TIME = re.compile(r"creation_time\s*:\s*(\d{4}-\d{2}-\d{2})[T ](\d{2}:\d{2}:\d{2})")
RE_LOCATION_FFMPEG = re.compile(
    r"^\s*(?:location-eng|location|com\.apple\.quicktime\.location\.ISO6709)\s*:\s*(.+?)\s*$",
    re.MULTILINE,
)
RE_ISO6709 = re.compile(r"([+-]\d{1,3}(?:\.\d+)?)([+-]\d{1,3}(?:\.\d+)?)(?:([+-]\d+(?:\.\d+)?))?/?")

RE_XMP_GPS_LAT = re.compile(r'<exif:GPSLatitude[^>]*>([^<]+)</exif:GPSLatitude>')
RE_XMP_GPS_LON = re.compile(r'<exif:GPSLongitude[^>]*>([^<]+)</exif:GPSLongitude>')
RE_XMP_GPS_LAT_ATTR = re.compile(r'exif:GPSLatitude="([^"]+)"')
RE_XMP_GPS_LON_ATTR = re.compile(r'exif:GPSLongitude="([^"]+)"')
RE_XMP_DATA = re.compile(
    r'<(?:xmp:CreateDate|photoshop:DateCreated|exif:DateTimeOriginal)[^>]*>([^<]+)</'
    r'(?:xmp:CreateDate|photoshop:DateCreated|exif:DateTimeOriginal)>'
)
RE_XMP_DATA_ATTR = re.compile(
    r'(?:xmp:CreateDate|photoshop:DateCreated|exif:DateTimeOriginal)="([^"]+)"'
)

PNG_CHAVES_DATA = {"creation time", "creationtime", "date:create", "date:modify"}


def registrar_heif():
    try:
        import pillow_heif
        pillow_heif.register_heif_opener()
        return True
    except ImportError:
        return False


def gms_para_decimal(valor, ref):
    try:
        partes = [float(v) for v in valor]
        if len(partes) < 2:
            return None
        dec = partes[0] + partes[1] / 60.0 + (partes[2] if len(partes) > 2 else 0.0) / 3600.0
        if str(ref).strip().upper() in ("S", "W"):
            dec = -dec
        return dec
    except (TypeError, ValueError):
        return None


def ler_gps_exif(exif):
    try:
        ifd = exif.get_ifd(0x8825)
        if not ifd:
            return None
        lat = gms_para_decimal(ifd.get(2), ifd.get(1))
        lon = gms_para_decimal(ifd.get(4), ifd.get(3))
        if lat is None or lon is None:
            return None
        return lat, lon
    except Exception:
        return None


def parsear_iso6709(texto):
    """Parseia coordenadas ISO 6709 (padrão de GPS em vídeos: ©xyz do QuickTime).

    Formatos aceitos: "+23.5500-046.6333+000/", "-23.55-046.63/", "+23.5500-046.6333/".
    Retorna (lat, lon) ou None (0,0 é tratado como ausente).
    """
    m = RE_ISO6709.search(str(texto).strip())
    if not m:
        return None
    try:
        lat = float(m.group(1))
        lon = float(m.group(2))
    except ValueError:
        return None
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        return None
    if lat == 0 and lon == 0:
        return None
    return lat, lon


def parsear_data_iso(texto):
    """Parseia datas ISO/EXIF flexíveis (com ou sem hora, ignora fuso/fração).

    Ex.: "2021-06-15T12:34:56Z", "2021-06-15T12:34:56-03:00", "2021:06:15 12:34:56",
    "2021-06-15T12:34:56.123", "2021-03-15".
    """
    s = re.sub(r"\s+", " ", str(texto).strip())
    m = re.match(r"^(\d{4})[-:](\d{2})[-:](\d{2})(?:[T ](\d{2})[.:](\d{2})[.:](\d{2}))?", s)
    if not m:
        return None
    return montar_dt(m.group(1), m.group(2), m.group(3),
                     m.group(4) or 0, m.group(5) or 0, m.group(6) or 0)


def _decimal_xmp(valor):
    """Converte latitude/longitude XMP ("23,33.5S" ou "23.55833S") para decimal."""
    s = str(valor).strip().upper()
    m = re.match(
        r"^([0-9]+(?:[.,][0-9]+)?)(?:,([0-9]+(?:[.,][0-9]+)?))?"
        r"(?:,([0-9]+(?:[.,][0-9]+)?))?\s*([NSEW])$", s,
    )
    if not m:
        return None
    gr = float(m.group(1).replace(",", "."))
    mi = float(m.group(2).replace(",", ".")) if m.group(2) else 0.0
    se = float(m.group(3).replace(",", ".")) if m.group(3) else 0.0
    dec = gr + mi / 60.0 + se / 3600.0
    if m.group(4) in ("S", "W"):
        dec = -dec
    return dec


def _xmp_como_dict(img):
    try:
        xmp = img.getxmp()
    except Exception:
        return None
    return xmp or None


def _descriptions_xmp(xmp_dict):
    try:
        rdf = (xmp_dict.get("xmpmeta", xmp_dict) or {}).get("RDF", {})
    except AttributeError:
        return []
    descs = rdf.get("Description", [])
    if isinstance(descs, dict):
        descs = [descs]
    return [d for d in descs if isinstance(d, dict)]


def gps_xmp(img):
    """GPS lido do bloco XMP (comum em PNGs e em arquivos processados por editores)."""
    xmp = _xmp_como_dict(img)
    if not xmp:
        return None
    if isinstance(xmp, dict):
        for desc in _descriptions_xmp(xmp):
            lat = _decimal_xmp(desc.get("GPSLatitude"))
            lon = _decimal_xmp(desc.get("GPSLongitude"))
            if lat is not None and lon is not None:
                return lat, lon
        return None
    lat = RE_XMP_GPS_LAT.search(xmp) or RE_XMP_GPS_LAT_ATTR.search(xmp)
    lon = RE_XMP_GPS_LON.search(xmp) or RE_XMP_GPS_LON_ATTR.search(xmp)
    if not lat or not lon:
        return None
    lat_dec = _decimal_xmp(lat.group(1))
    lon_dec = _decimal_xmp(lon.group(1))
    if lat_dec is None or lon_dec is None:
        return None
    return lat_dec, lon_dec


def datas_xmp(img):
    """Datas do bloco XMP (CreateDate, DateCreated, DateTimeOriginal)."""
    xmp = _xmp_como_dict(img)
    if not xmp:
        return []
    if isinstance(xmp, dict):
        datas = []
        for desc in _descriptions_xmp(xmp):
            for chave in ("DateTimeOriginal", "CreateDate", "DateCreated"):
                valor = desc.get(chave)
                if not valor:
                    continue
                if isinstance(valor, list):
                    valor = valor[0] if valor else None
                if not valor:
                    continue
                dt = parsear_data_iso(valor)
                if dt:
                    datas.append(dt)
        return datas
    datas = []
    for m in RE_XMP_DATA.finditer(xmp):
        dt = parsear_data_iso(m.group(1))
        if dt:
            datas.append(dt)
    for m in RE_XMP_DATA_ATTR.finditer(xmp):
        dt = parsear_data_iso(m.group(1))
        if dt:
            datas.append(dt)
    return datas


def datas_png_text(img):
    """Datas dos metadados de texto PNG (tEXt/iTXt: "Creation Time", "date:create"...)."""
    try:
        texto = img.text or {}
    except Exception:
        return []
    datas = []
    for chave, valor in texto.items():
        if str(chave).strip().lower() not in PNG_CHAVES_DATA:
            continue
        dt = parsear_data_iso(valor)
        if dt is None:
            try:
                dt = datetime.strptime(str(valor).strip(), "%a %b %d %H:%M:%S %Y")
                if not dentro_do_periodo(dt):
                    dt = None
            except ValueError:
                dt = None
        if dt:
            datas.append(dt)
    return datas


def metadados_imagem(caminho):
    """Retorna (datas, gps) lidos dos metadados da imagem (EXIF, XMP e texto PNG)."""
    datas, gps = [], None
    try:
        with Image.open(caminho) as img:
            exif = img.getexif()
            for tag in (36867, 36868, 306):
                valor = exif.get(tag)
                if valor:
                    dt = parsear_data_exif(valor)
                    if dt:
                        datas.append(dt)
            gps = ler_gps_exif(exif)
            if gps is None:
                gps = gps_xmp(img)
            datas.extend(datas_xmp(img))
            if img.format == "PNG":
                datas.extend(datas_png_text(img))
    except Exception as e:
        logging.debug("Falha ao ler metadados da imagem %s: %s", caminho, e)
    return (datas or None), gps


def metadados_video(caminho):
    """Retorna (data_criacao, gps) lidos dos metadados do vídeo (ffmpeg).

    - Data: creation_time do container.
    - GPS: localização em ISO 6709 (location / ©xyz do QuickTime),
      comum em vídeos de iPhone/Android.
    """
    if not FFMPEG_EXE:
        return None, None
    try:
        r = subprocess.run(
            [FFMPEG_EXE, "-hide_banner", "-i", str(caminho), "-f", "null", "-"],
            capture_output=True, text=True, timeout=180,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None, None
    stderr = r.stderr or ""
    dt = None
    m = RE_CREATION_TIME.search(stderr)
    if m:
        dt = montar_dt(m.group(1)[:4], m.group(1)[5:7], m.group(1)[8:10],
                       m.group(2)[:2], m.group(2)[3:5], m.group(2)[6:8])
    gps = None
    m = RE_LOCATION_FFMPEG.search(stderr)
    if m:
        gps = parsear_iso6709(m.group(1))
    return dt, gps


def metadados_exiftool(caminho):
    """Fallback opcional: lê datas e GPS com o binário exiftool, se instalado.

    exiftool (Phil Harvey) é o padrão de referência em perícia forense;
    usado aqui apenas quando Pillow/ffmpeg não encontraram nada.
    """
    if not EXIFTOOL_EXE:
        return None, None
    try:
        r = subprocess.run(
            [EXIFTOOL_EXE, "-j", "-G", "-n", str(caminho)],
            capture_output=True, text=True, timeout=60,
        )
        if r.returncode != 0:
            return None, None
        dados = json.loads(r.stdout or "")
    except (OSError, ValueError, json.JSONDecodeError):
        return None, None
    reg = dados[0] if isinstance(dados, list) and dados else {}
    datas = []
    for chave in ("EXIF:DateTimeOriginal", "EXIF:CreateDate", "EXIF:ModifyDate",
                  "QuickTime:CreateDate", "QuickTime:CreationDate", "XMP:CreateDate",
                  "PNG:CreationTime", "IPTC:DateCreated"):
        valor = reg.get(chave)
        if valor:
            dt = parsear_data_iso(valor)
            if dt:
                datas.append(dt)
    gps = None
    pos = reg.get("Composite:GPSPosition") or reg.get("EXIF:GPSPosition")
    if isinstance(pos, str):
        partes = pos.split()
        if len(partes) >= 2:
            try:
                gps = (float(partes[0]), float(partes[1]))
            except ValueError:
                gps = None
    if gps is None:
        try:
            lat = float(reg.get("EXIF:GPSLatitude", reg.get("XMP:GPSLatitude", 0)))
            lon = float(reg.get("EXIF:GPSLongitude", reg.get("XMP:GPSLongitude", 0)))
            if str(reg.get("EXIF:GPSLatitudeRef", "")).strip().upper() == "S":
                lat = -lat
            if str(reg.get("EXIF:GPSLongitudeRef", "")).strip().upper() == "W":
                lon = -lon
            gps = (lat, lon)
        except (TypeError, ValueError):
            gps = None
    if gps and gps[0] == 0 and gps[1] == 0:
        gps = None
    return (datas or None), gps


def data_filesystem(caminho):
    """Última alternativa: data do sistema de arquivos (min entre criação/modificação)."""
    try:
        st = caminho.stat()
        timestamps = [t for t in (st.st_ctime, st.st_mtime) if t]
        if not timestamps:
            return None
        dt = datetime.fromtimestamp(min(timestamps))
    except (OSError, ValueError, OverflowError):
        return None
    return dt if dentro_do_periodo(dt) else None
