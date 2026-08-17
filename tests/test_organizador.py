#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Testes de integração do organizador (sem IA e sem rede)."""

from datetime import datetime
from pathlib import Path

import pytest
from PIL import Image

from py_photos_organize_tpv import geolocalizacao, ia, metadados
from py_photos_organize_tpv.organizador import (
    Config,
    classificar_sufixo,
    coletar_arquivos,
    montar_pasta_destino,
    obter_datas,
    organizar,
)


@pytest.fixture
def origem_com_imagens(tmp_path):
    origem = tmp_path / "origem"
    origem.mkdir()
    foto = origem / "foto_praia.jpg"
    Image.new("RGB", (64, 64), (255, 0, 0)).save(foto)
    com_exif = origem / "viagem_2019_07_04_08h09m10s.jpg"
    img = Image.new("RGB", (64, 64), (0, 255, 0))
    exif = Image.Exif()
    exif[36867] = "2021:03:15 10:20:30"
    img.save(com_exif, exif=exif)
    (origem / "ignorado.exe").write_text("não deve ser processado", encoding="utf-8")
    sub = origem / "subpasta"
    sub.mkdir()
    Image.new("RGB", (32, 32), (0, 0, 255)).save(sub / "IMG-20190315-WA0000.jpg")
    return origem


def _config(origem, destino, **kwargs):
    padrao = dict(
        origem=origem,
        destino=destino,
        usar_ia=False,
        min_size_low_res=0,
        cache_titulos_path=str(destino.parent / "cache_titulos.jsonl"),
        cache_gps_path=str(destino.parent / "cache_gps.json"),
    )
    padrao.update(kwargs)
    return Config(**padrao)


def test_coletar_arquivos(origem_com_imagens):
    arquivos = coletar_arquivos(origem_com_imagens)
    nomes = {p.name for p in arquivos}
    assert nomes == {"foto_praia.jpg", "viagem_2019_07_04_08h09m10s.jpg", "IMG-20190315-WA0000.jpg"}


def test_classificar_sufixo():
    assert classificar_sufixo(Path("x/video.mp4"), 10 ** 8, 100000) == "videos"
    assert classificar_sufixo(Path("x/Screenshot_1.jpg"), 10 ** 6, 100000) == "screen_capture"
    assert classificar_sufixo(Path("x/insta_post.jpg"), 10 ** 6, 100000) == "social_media"
    assert classificar_sufixo(Path("x/IMG-20190315-WA0000.jpg"), 10 ** 6, 100000) == "instant_messages"
    assert classificar_sufixo(Path("x/pequena.jpg"), 50000, 100000) == "low_resolution"
    assert classificar_sufixo(Path("x/normal.jpg"), 10 ** 6, 100000) is None
    assert classificar_sufixo(Path("x/audio.mp3"), 10 ** 6, 100000) == "audios"
    assert classificar_sufixo(Path("x/doc.pdf"), 10 ** 6, 100000) == "outros_tipos"


def test_obter_datas_exif_prioritario(origem_com_imagens):
    d_min, d_max, gps = obter_datas(origem_com_imagens / "viagem_2019_07_04_08h09m10s.jpg", 1980)
    assert gps is None
    assert d_min == datetime(2019, 7, 4, 8, 9, 10)
    assert d_max == datetime(2021, 3, 15, 10, 20, 30)


def test_obter_datas_nome(origem_com_imagens):
    d_min, d_max, _ = obter_datas(origem_com_imagens / "foto_praia.jpg", 1980)
    assert d_min == d_max


def test_obter_datas_sem_nenhuma_fonte(origem_com_imagens, monkeypatch):
    monkeypatch.setattr(metadados, "data_filesystem", lambda caminho: None)
    d_min, d_max, _ = obter_datas(origem_com_imagens / "foto_praia.jpg", 1980)
    assert d_min is None and d_max is None


def test_montar_pasta_destino():
    destino = Path("E:/out")
    assert montar_pasta_destino(destino, datetime(2023, 5, 1), "%Y_%m", None) == destino / "2023_05"
    assert (montar_pasta_destino(destino, datetime(2023, 5, 1), "%Y_%m", "videos")
            == destino / "2023_05-videos")
    assert montar_pasta_destino(destino, None, "%Y_%m", None) == destino / "sem_data"


def test_organizar_formato_alvo(origem_com_imagens, tmp_path):
    destino = tmp_path / "destino"
    cfg = _config(origem_com_imagens, destino)
    estats = organizar(cfg)
    assert estats.total == 3
    assert estats.copiados == 3
    assert estats.erros == 0

    alvo_viagem = destino / "2019_07" / ("2019_07_04_08h09m10s-2021_03_15_10h20m30s-"
                                          "sem_gps.jpg")
    # data1 vem do nome (2019), data2 do EXIF (2021); sem IA, não há título
    assert alvo_viagem.exists()

    wa = destino / "2019_03-instant_messages"
    arquivos_wa = list(wa.glob("*.jpg"))
    assert len(arquivos_wa) == 1
    nome_wa = arquivos_wa[0].name
    assert nome_wa == "2019_03_15_00h00m00s-2019_03_15_00h00m00s-sem_gps.jpg"


def test_organizar_duplicar_e_ignorar(origem_com_imagens, tmp_path):
    destino = tmp_path / "destino"
    cfg = _config(origem_com_imagens, destino, overwrite="d")
    organizar(cfg)
    estats2 = organizar(cfg)
    assert estats2.copiados == 3
    for p in destino.rglob("*.jpg"):
        duplicados = list(p.parent.glob(f"{p.stem}_*{p.suffix}"))
        assert len(duplicados) >= 1
        break

    destino3 = tmp_path / "destino3"
    cfg3 = _config(origem_com_imagens, destino3, overwrite="i")
    organizar(cfg3)
    estats4 = organizar(cfg3)
    assert estats4.ignorados == 3
    assert sum(1 for _ in destino3.rglob("*.jpg")) == 3


def test_organizar_dry_run_nao_altera(origem_com_imagens, tmp_path):
    destino = tmp_path / "destino"
    cfg = _config(origem_com_imagens, destino, dry_run=True)
    estats = organizar(cfg)
    assert estats.copiados == 3
    assert not destino.exists() or not any(destino.rglob("*.jpg"))


def test_organizar_renomear_desativado(origem_com_imagens, tmp_path):
    destino = tmp_path / "destino"
    cfg = _config(origem_com_imagens, destino, renomear=False)
    organizar(cfg)
    assert (destino / "2019_03" / "IMG-20190315-WA0000.jpg").exists() or \
        any(destino.rglob("IMG-20190315-WA0000.jpg"))


def test_organizar_sem_data_mantem_nome(origem_com_imagens, tmp_path, monkeypatch):
    monkeypatch.setattr(metadados, "data_filesystem", lambda caminho: None)
    destino = tmp_path / "destino"
    cfg = _config(origem_com_imagens, destino)
    organizar(cfg)
    assert (destino / "sem_data" / "foto_praia.jpg").exists()


def test_obter_titulo_sem_ia(origem_com_imagens, tmp_path):
    cache = {}
    cache_path = tmp_path / "cache_titulos.jsonl"
    titulo = ia.obter_titulo(origem_com_imagens / "foto_praia.jpg", "imagem", None, cache,
                             str(cache_path))
    assert titulo == ""
    assert not cache_path.exists()


def test_obter_titulo_ia_indisponivel_sem_cache(origem_com_imagens, tmp_path):
    cache = {}
    cache_path = tmp_path / "cache_titulos.jsonl"
    contexto = {"openai": object()}
    titulo = ia.obter_titulo(origem_com_imagens / "foto_praia.jpg", "imagem", contexto,
                             cache, str(cache_path))
    assert titulo == ""
    assert not cache_path.exists()


def test_obter_titulo_com_cache_sem_nova_chamada(origem_com_imagens, tmp_path, monkeypatch):
    cache_path = tmp_path / "cache_titulos.jsonl"
    cache = ia.carregar_cache_titulos(str(cache_path))
    sha = ia.sha256_arquivo(origem_com_imagens / "foto_praia.jpg")
    contexto = {"openai": object()}
    cache[sha] = {"sha256": sha, "titulo": "titulo_cacheados"}
    titulo = ia.obter_titulo(origem_com_imagens / "foto_praia.jpg", "imagem", contexto, cache,
                             str(cache_path))
    assert titulo == "titulo_cacheados"


def test_cache_titulos_reutiliza_por_sha256(origem_com_imagens, tmp_path):
    cache_path = tmp_path / "cache_titulos.jsonl"
    ia.gravar_cache_titulos({"sha256": "abc123", "titulo": "praia"}, str(cache_path))
    cache = ia.carregar_cache_titulos(str(cache_path))
    assert cache["abc123"]["titulo"] == "praia"


def test_sha256_arquivo(tmp_path):
    p = tmp_path / "a.txt"
    p.write_text("conteudo", encoding="utf-8")
    import hashlib
    esperado = hashlib.sha256(b"conteudo").hexdigest()
    assert ia.sha256_arquivo(p) == esperado
    assert ia.sha256_arquivo(tmp_path / "nao_existe.txt") is None


def test_cidade_ou_coordenadas_com_cache(monkeypatch):
    cache = {"-23.55000,-46.63333": "São Paulo"}
    monkeypatch.setattr(geolocalizacao, "cidade_por_gps", lambda lat, lon, cache, cache_path: cache.get(f"{lat:.5f},{lon:.5f}"))
    assert geolocalizacao.cidade_ou_coordenadas(-23.55, -46.633333, cache) == "sao_paulo"


def test_cidade_ou_coordenadas_sem_resposta(monkeypatch):
    monkeypatch.setattr(geolocalizacao, "cidade_por_gps", lambda lat, lon, cache, cache_path: None)
    resultado = geolocalizacao.cidade_ou_coordenadas(-23.55, -46.633333, {})
    assert resultado == "-23_5500_-46_6333"
