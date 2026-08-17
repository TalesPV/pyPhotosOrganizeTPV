#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Testes de extração de metadados (EXIF, GPS, XMP, PNG, vídeo, sistema de arquivos)."""

import json
import subprocess
from datetime import datetime

import pytest
from PIL import Image

from py_photos_organize_tpv import metadados
from py_photos_organize_tpv.metadados import (
    data_filesystem,
    gms_para_decimal,
    ler_gps_exif,
    metadados_imagem,
    metadados_video,
    parsear_data_iso,
    parsear_iso6709,
)


def _criar_imagem_com_exif(caminho, datetime_original="2021:03:15 10:20:30", gps=None):
    img = Image.new("RGB", (64, 64), (255, 0, 0))
    exif = Image.Exif()
    exif[36867] = datetime_original
    if gps:
        ifd = exif.get_ifd(0x8825)
        ifd[1] = gps["lat_ref"]
        ifd[2] = gps["lat"]
        ifd[3] = gps["lon_ref"]
        ifd[4] = gps["lon"]
        exif[0x8825] = ifd
    img.save(caminho, exif=exif)


def test_metadados_imagem_sem_exif(tmp_path):
    caminho = tmp_path / "sem_exif.jpg"
    Image.new("RGB", (32, 32), (0, 255, 0)).save(caminho)
    datas, gps = metadados_imagem(caminho)
    assert datas is None
    assert gps is None


def test_metadados_imagem_com_exif(tmp_path):
    caminho = tmp_path / "com_exif.jpg"
    _criar_imagem_com_exif(caminho)
    datas, gps = metadados_imagem(caminho)
    assert datas is not None
    assert min(datas) == datetime(2021, 3, 15, 10, 20, 30)
    assert gps is None


def test_metadados_imagem_com_gps(tmp_path):
    caminho = tmp_path / "com_gps.jpg"
    _criar_imagem_com_exif(caminho, gps={
        "lat_ref": "S", "lat": (23.0, 33.0, 0.0),
        "lon_ref": "W", "lon": (46.0, 38.0, 0.0),
    })
    datas, gps = metadados_imagem(caminho)
    assert gps is not None
    lat, lon = gps
    assert lat == pytest.approx(-23.55, abs=1e-6)
    assert lon == pytest.approx(-46.6333333, abs=1e-6)


def test_gms_para_decimal():
    assert gms_para_decimal((23, 33, 0), "S") == pytest.approx(-23.55)
    assert gms_para_decimal((46, 38, 0), "W") == pytest.approx(-46.63333333)
    assert gms_para_decimal((0, 0), "N") == 0.0
    assert gms_para_decimal(("a", "b"), "N") is None


def test_ler_gps_exif_sem_gps(tmp_path):
    caminho = tmp_path / "sem_gps.jpg"
    _criar_imagem_com_exif(caminho)
    with Image.open(caminho) as img:
        assert ler_gps_exif(img.getexif()) is None


def test_data_filesystem(tmp_path):
    caminho = tmp_path / "arquivo.txt"
    caminho.write_text("x", encoding="utf-8")
    dt = data_filesystem(caminho)
    assert dt is not None
    assert datetime(2020, 1, 1) <= dt <= datetime.now()


def test_data_filesystem_inexistente(tmp_path):
    assert data_filesystem(tmp_path / "nao_existe.txt") is None


def test_extensoes_suportadas():
    assert ".jpg" in metadados.EXTS_IMAGEM
    assert ".heic" in metadados.EXTS_IMAGEM
    assert ".mp4" in metadados.EXTS_VIDEO
    assert ".pdf" in metadados.EXTS_OUTROS
    assert ".mp3" in metadados.EXTS_AUDIO


@pytest.mark.parametrize("texto,esperado", [
    ("+23.5500-046.6333+000/", (23.55, -46.6333)),
    ("+23.5500-046.6333/", (23.55, -46.6333)),
    ("-23.55-046.63/", (-23.55, -46.63)),
    ("+40.7486-073.9864+033.7/", (40.7486, -73.9864)),
    ("+00.0000+000.0000+000/", None),
    ("sem localizacao", None),
])
def test_parsear_iso6709(texto, esperado):
    if esperado is None:
        assert parsear_iso6709(texto) is None
    else:
        lat, lon = parsear_iso6709(texto)
        assert lat == pytest.approx(esperado[0])
        assert lon == pytest.approx(esperado[1])


@pytest.mark.parametrize("texto,esperado", [
    ("2021-06-15T12:34:56Z", datetime(2021, 6, 15, 12, 34, 56)),
    ("2021-06-15T12:34:56-03:00", datetime(2021, 6, 15, 12, 34, 56)),
    ("2021:06:15 12:34:56", datetime(2021, 6, 15, 12, 34, 56)),
    ("2021-06-15T12:34:56.123", datetime(2021, 6, 15, 12, 34, 56)),
    ("2021-03-15", datetime(2021, 3, 15)),
    ("2021-03-15T12:34:56.123+02:00", datetime(2021, 3, 15, 12, 34, 56)),
    ("sem data", None),
])
def test_parsear_data_iso(texto, esperado):
    assert parsear_data_iso(texto) == esperado


_XMP_GPS = (
    '<?xpacket begin="\ufeff" id="W5M0MpCehiHzreSzNTczkc9d"?>'
    '<x:xmpmeta xmlns:x="adobe:ns:meta/">'
    '<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">'
    '<rdf:Description xmlns:exif="http://ns.adobe.com/exif/1.0/" '
    'exif:GPSLatitude="23,33.5S" exif:GPSLongitude="46,38.5W" '
    'exif:DateTimeOriginal="2020:01:02 03:04:05"/>'
    '</rdf:RDF></x:xmpmeta>'
)


def test_metadados_imagem_gps_e_data_xmp(tmp_path):
    caminho = tmp_path / "com_xmp.jpg"
    img = Image.new("RGB", (32, 32), (0, 0, 255))
    img.save(caminho, xmp=_XMP_GPS.encode("utf-8"))
    datas, gps = metadados_imagem(caminho)
    assert gps is not None
    lat, lon = gps
    assert lat == pytest.approx(-23.5583333, abs=1e-6)
    assert lon == pytest.approx(-46.6416667, abs=1e-6)
    assert datetime(2020, 1, 2, 3, 4, 5) in datas


def test_metadados_imagem_sem_gps_sem_xmp(tmp_path):
    caminho = tmp_path / "sem_xmp.jpg"
    Image.new("RGB", (32, 32), (0, 255, 0)).save(caminho)
    datas, gps = metadados_imagem(caminho)
    assert gps is None
    assert datas is None


def test_metadados_imagem_png_text_date(tmp_path):
    from PIL import PngImagePlugin
    caminho = tmp_path / "captura.png"
    pnginfo = PngImagePlugin.PngInfo()
    pnginfo.add_text("Creation Time", "2021-06-15T12:34:56Z")
    pnginfo.add_text("Software", "Firefox")
    Image.new("RGB", (32, 32), (0, 0, 0)).save(caminho, pnginfo=pnginfo)
    datas, _ = metadados_imagem(caminho)
    assert datetime(2021, 6, 15, 12, 34, 56) in datas


def test_metadados_video_sem_gps(tmp_path):
    import subprocess
    import imageio_ffmpeg
    ff = imageio_ffmpeg.get_ffmpeg_exe()
    video = tmp_path / "sem_location.mp4"
    subprocess.run([ff, "-y", "-loglevel", "error", "-f", "lavfi",
                    "-i", "testsrc=size=64x64:rate=5", "-t", "1", str(video)],
                   check=True, capture_output=True)
    dt, gps = metadados_video(video)
    assert dt is None
    assert gps is None


def test_metadados_video_com_location(tmp_path):
    import subprocess
    import imageio_ffmpeg
    ff = imageio_ffmpeg.get_ffmpeg_exe()
    video = tmp_path / "com_location.mp4"
    subprocess.run(
        [ff, "-y", "-loglevel", "error", "-f", "lavfi",
         "-i", "testsrc=size=64x64:rate=5", "-t", "1",
         "-metadata", "location=+23.5500-046.6333+000/",
         "-metadata", "creation_time=2021-06-15T12:34:56Z",
         "-movflags", "use_metadata_tags", str(video)],
        check=True, capture_output=True,
    )
    dt, gps = metadados_video(video)
    assert dt == datetime(2021, 6, 15, 12, 34, 56)
    assert gps is not None
    lat, lon = gps
    assert lat == pytest.approx(23.55)
    assert lon == pytest.approx(-46.6333)


def test_metadados_exiftool_parse(tmp_path, monkeypatch):
    json_fake = json.dumps([{
        "SourceFile": "foto.jpg",
        "EXIF:DateTimeOriginal": "2021:03:15 10:20:30",
        "Composite:GPSPosition": "23.5500 -46.633333",
    }])
    monkeypatch.setattr(metadados, "EXIFTOOL_EXE", "exiftool")
    monkeypatch.setattr(metadados.subprocess, "run",
                        lambda *a, **k: subprocess.CompletedProcess(a[0], 0, stdout=json_fake))
    datas, gps = metadados.metadados_exiftool(tmp_path / "foto.jpg")
    assert min(datas) == datetime(2021, 3, 15, 10, 20, 30)
    lat, lon = gps
    assert lat == pytest.approx(23.55)
    assert lon == pytest.approx(-46.633333)


def test_metadados_exiftool_sem_binario(tmp_path, monkeypatch):
    monkeypatch.setattr(metadados, "EXIFTOOL_EXE", None)
    assert metadados.metadados_exiftool(tmp_path / "foto.jpg") == (None, None)
