#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Testes de integração do organizador (sem IA e sem rede)."""

from datetime import datetime
from pathlib import Path

import pytest
from PIL import Image
from pereiras_common import geolocalizacao, metadados
from pereiras_common.nomeacao import montar_pasta_destino
from pereiras_common.metadados import classificar_sufixo, obter_datas

from py_photos_organize_tpv import ia
from py_photos_organize_tpv.organizador import (
    Config,
    coletar_arquivos,
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
    assert classificar_sufixo(Path("x/video.mp4"), tamanho=10 ** 8, min_size_low_res=100000) == "videos"
    assert classificar_sufixo(Path("x/Screenshot_1.jpg"), tamanho=10 ** 6, min_size_low_res=100000) == "screen_capture"
    assert classificar_sufixo(Path("x/insta_post.jpg"), tamanho=10 ** 6, min_size_low_res=100000) == "social_media"
    assert classificar_sufixo(Path("x/IMG-20190315-WA0000.jpg"), tamanho=10 ** 6, min_size_low_res=100000) == "instant_messages"
    assert classificar_sufixo(Path("x/pequena.jpg"), tamanho=50000, min_size_low_res=100000) == "low_resolution"
    assert classificar_sufixo(Path("x/normal.jpg"), tamanho=10 ** 6, min_size_low_res=100000) is None
    assert classificar_sufixo(Path("x/audio.mp3"), tamanho=10 ** 6, min_size_low_res=100000) == "audios"
    assert classificar_sufixo(Path("x/doc.pdf"), tamanho=10 ** 6, min_size_low_res=100000) == "outros_tipos"


def test_obter_datas_exif_prioritario(origem_com_imagens):
    d_min, d_max, gps = obter_datas(origem_com_imagens / "viagem_2019_07_04_08h09m10s.jpg", 1980)
    assert gps is None
    assert d_min == datetime(2019, 7, 4, 8, 9, 10)
    assert d_max == datetime(2021, 3, 15, 10, 20, 30)


def test_obter_datas_nome(origem_com_imagens):
    d_min, d_max, _ = obter_datas(origem_com_imagens / "foto_praia.jpg", 1980)
    assert d_min == d_max


def test_obter_datas_audio_metadados(tmp_path):
    import imageio_ffmpeg
    import subprocess
    ff = imageio_ffmpeg.get_ffmpeg_exe()
    audio = tmp_path / "musica.mp3"
    r = subprocess.run(
        [ff, "-y", "-loglevel", "error", "-f", "lavfi",
         "-i", "sine=frequency=440:duration=1",
         "-c:a", "libmp3lame", "-write_id3v2", "1", "-id3v2_version", "4",
         "-metadata", "date=2021-06-15T12:34:56", str(audio)],
        capture_output=True,
    )
    if r.returncode != 0:
        pytest.skip("ffmpeg sem suporte a MP3")
    d_min, d_max, gps = obter_datas(audio, 1980)
    assert d_min == datetime(2021, 6, 15, 12, 34, 56)
    assert d_max == d_min
    assert gps is None


def test_obter_datas_sem_nenhuma_fonte(origem_com_imagens, monkeypatch):
    monkeypatch.setattr(metadados, "data_filesystem", lambda caminho, ano_minimo=1980: None)
    d_min, d_max, _ = obter_datas(origem_com_imagens / "foto_praia.jpg", 1980)
    assert d_min is None and d_max is None


def test_montar_pasta_destino():
    destino = Path("E:/out")
    assert montar_pasta_destino(destino, datetime(2023, 5, 1), "%Y_%m", None) == destino / "2023_05"
    assert (montar_pasta_destino(destino, datetime(2023, 5, 1), "%Y_%m", "videos")
            == destino / "2023_05-videos")
    assert montar_pasta_destino(destino, None, "%Y_%m", None) == destino / "sem_data"


def test_organizar_formato_alvo(origem_com_imagens, tmp_path):
    from pereiras_common.uteis import hash_curto_6
    destino = tmp_path / "destino"
    cfg = _config(origem_com_imagens, destino)
    estats = organizar(cfg)
    assert estats.total == 3
    assert estats.copiados == 3
    assert estats.erros == 0

    hash_viagem = hash_curto_6(origem_com_imagens / "viagem_2019_07_04_08h09m10s.jpg")
    alvo_viagem = destino / "2019_07" / ("2019_07_04_08h09m10s-2021_03_15_10h20m30s-"
                                          f"sem_gps-{hash_viagem}.jpg")
    # data1 vem do nome (2019), data2 do EXIF (2021); sem IA, não há título
    assert alvo_viagem.exists()

    wa_origem = origem_com_imagens / "subpasta" / "IMG-20190315-WA0000.jpg"
    hash_wa = hash_curto_6(wa_origem)
    wa = destino / "2019_03-instant_messages"
    arquivos_wa = list(wa.glob("*.jpg"))
    assert len(arquivos_wa) == 1
    nome_wa = arquivos_wa[0].name
    assert nome_wa == f"2019_03_15_00h00m00s-2019_03_15_00h00m00s-sem_gps-{hash_wa}.jpg"


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
    monkeypatch.setattr(metadados, "data_filesystem", lambda caminho, ano_minimo=1980: None)
    destino = tmp_path / "destino"
    cfg = _config(origem_com_imagens, destino)
    organizar(cfg)
    assert (destino / "sem_data" / "foto_praia.jpg").exists()


def test_obter_titulo_imagem_usa_analise_compartilhada(origem_com_imagens, tmp_path, monkeypatch):
    from pereiras_common.ia import AnaliseFoto
    chamadas = []

    def fake_analisar(chave, tipo_ia, caminho):
        chamadas.append((tipo_ia, caminho))
        return AnaliseFoto(titulo="praia_ensolarada", resumo="x", nivel=1,
                           motivo="x", modelo="gpt-4o-mini")

    monkeypatch.setattr(ia, "analisar_foto", fake_analisar)
    contexto = {"openai": object(), "chave_openai": "CHAVE-OPENAI-123456"}
    cache = {}
    cache_path = tmp_path / "cache_titulos.jsonl"
    titulo = ia.obter_titulo(origem_com_imagens / "foto_praia.jpg", "imagem", contexto,
                             cache, str(cache_path))
    assert titulo == "praia_ensolarada"
    assert chamadas and chamadas[0][0] == "openai"


def test_organizar_outros_mantem_nome(tmp_path):
    """Arquivos que não são mídia (txt/pdf/office) NUNCA são renomeados."""
    origem = tmp_path / "origem"
    origem.mkdir()
    documento = origem / "contrato_2020_01_02.txt"
    documento.write_text("texto", encoding="utf-8")
    destino = tmp_path / "destino"
    cfg = _config(origem, destino)
    estats = organizar(cfg)
    assert estats.copiados == 1
    copias = list(destino.rglob("contrato_2020_01_02.txt"))
    assert len(copias) == 1


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


# ------------------------------------- dry-run com --mover conta como movido

def test_dry_run_mover_conta_como_movido(origem_com_imagens, tmp_path):
    """No dry-run de --mover o resumo precisa dizer "movidos", não "copiados"."""
    destino = tmp_path / "destino"
    cfg = _config(origem_com_imagens, destino, dry_run=True, mover=True)
    estats = organizar(cfg)
    assert estats.movidos == 3
    assert estats.copiados == 0
    # Nada pode ter saído do lugar num dry-run.
    assert sum(1 for _ in origem_com_imagens.rglob("*.jpg")) == 3


# ---------------------------------- origem igual ao destino é sinalizado

def test_organizar_avisa_quando_origem_e_destino_sao_a_mesma_pasta(
        origem_com_imagens, caplog):
    """Copiar dentro da própria origem duplica a coleção: precisa avisar."""
    cfg = _config(origem_com_imagens, origem_com_imagens, dry_run=True)
    with caplog.at_level("WARNING"):
        organizar(cfg)
    assert any("origem" in r.message.lower() and "destino" in r.message.lower()
               for r in caplog.records), "nenhum aviso sobre origem == destino"


# ------------------------- SHA-256 calculado uma única vez por arquivo

def test_obter_titulo_aceita_sha_ja_calculado(origem_com_imagens, tmp_path, monkeypatch):
    """Com o SHA-256 pronto, obter_titulo não relê o arquivo do disco."""
    foto = origem_com_imagens / "foto_praia.jpg"
    cache_path = tmp_path / "cache.jsonl"
    sha = ia.sha256_arquivo(foto)

    def _proibido(*_a, **_k):
        raise AssertionError("sha256_arquivo foi chamado de novo (leitura duplicada)")

    monkeypatch.setattr(ia, "sha256_arquivo", _proibido)
    cache = {sha: {"sha256": sha, "titulo": "praia_ao_por_do_sol"}}
    titulo = ia.obter_titulo(foto, "imagem", {"chave_openai": "x"}, cache,
                             str(cache_path), sha=sha)
    assert titulo == "praia_ao_por_do_sol"


def test_organizador_nao_le_o_arquivo_duas_vezes(origem_com_imagens, tmp_path, monkeypatch):
    """O organizador calcula o SHA-256 uma vez e reaproveita no hash curto."""
    from py_photos_organize_tpv import organizador as org

    chamadas = []
    original = org.sha256_arquivo
    monkeypatch.setattr(org, "sha256_arquivo",
                        lambda c: (chamadas.append(c), original(c))[1])
    destino = tmp_path / "destino"
    organizar(_config(origem_com_imagens, destino))
    assert len(chamadas) == len(set(map(str, chamadas))), \
        f"mesmo arquivo hasheado mais de uma vez: {chamadas}"


# ------------------- não perder o título já presente no nome do arquivo

def test_sem_ia_mantem_o_titulo_que_ja_esta_no_nome(tmp_path):
    """Reprocessar sem IA não pode apagar um título gerado numa execução anterior."""
    origem = tmp_path / "origem"
    origem.mkdir()
    nome = "2019_07_04_08h09m10s-2019_07_04_08h09m10s-sem_gps-retrato_de_jovem.jpg"
    Image.new("RGB", (48, 48), (7, 7, 7)).save(origem / nome)

    destino = tmp_path / "destino"
    organizar(_config(origem, destino))  # usar_ia=False

    gerados = [p.name for p in destino.rglob("*.jpg")]
    assert gerados == [nome], f"o título se perdeu: {gerados}"


def test_sem_ia_ainda_renomeia_arquivo_sem_titulo(tmp_path):
    """Sem título a perder, a renomeação normal continua valendo (ganha o hash6)."""
    origem = tmp_path / "origem"
    origem.mkdir()
    nome = "2019_07_04_08h09m10s-2019_07_04_08h09m10s-sem_gps.jpg"
    Image.new("RGB", (48, 48), (8, 8, 8)).save(origem / nome)

    destino = tmp_path / "destino"
    organizar(_config(origem, destino))

    gerados = [p.name for p in destino.rglob("*.jpg")]
    assert len(gerados) == 1
    assert gerados[0] != nome, "deveria ter ganhado o bloco hash6"
    assert gerados[0].startswith("2019_07_04_08h09m10s-2019_07_04_08h09m10s-sem_gps-")


# ------------------- padrão de segurança: simula por padrão, age com --aplicar

def test_cli_simula_por_padrao(origem_com_imagens, tmp_path):
    """Sem --aplicar nada pode ser escrito: mesmo padrão do renomear_arquivos.py."""
    from py_photos_organize_tpv.main import criar_parser
    destino = tmp_path / "destino"
    args = criar_parser().parse_args(["-o", str(origem_com_imagens), "-d", str(destino)])
    assert args.aplicar is False
    cfg = _config(origem_com_imagens, destino, dry_run=not args.aplicar)
    organizar(cfg)
    assert not destino.exists() or not any(destino.rglob("*.jpg"))


def test_cli_age_com_aplicar(origem_com_imagens, tmp_path):
    from py_photos_organize_tpv.main import criar_parser
    destino = tmp_path / "destino"
    args = criar_parser().parse_args(["-o", str(origem_com_imagens),
                                      "-d", str(destino), "--aplicar"])
    assert args.aplicar is True
    organizar(_config(origem_com_imagens, destino, dry_run=not args.aplicar))
    assert len(list(destino.rglob("*.jpg"))) == 3


def test_cli_aceita_dry_run_como_compatibilidade(origem_com_imagens, tmp_path):
    """--dry-run continua válido (agora é o padrão) para não quebrar scripts antigos."""
    from py_photos_organize_tpv.main import criar_parser
    args = criar_parser().parse_args(["-o", str(origem_com_imagens), "--dry-run"])
    assert args.aplicar is False


def test_ano_minimo_vem_do_pacote_compartilhado():
    """Um só valor para os três programas: sem 1977 num e 1980 noutro."""
    from pereiras_common.nomeacao import ANO_MINIMO_PADRAO
    from py_photos_organize_tpv.main import criar_parser
    args = criar_parser().parse_args([])
    assert args.min_year_discart_date == ANO_MINIMO_PADRAO


# ----------------------------- IA só quando pedida explicitamente (--com-ia)

def test_ia_desligada_por_padrao():
    """Chamar a IA custa dinheiro: tem de ser escolha explícita."""
    from py_photos_organize_tpv.main import criar_parser
    args = criar_parser().parse_args([])
    assert args.com_ia is False


def test_com_ia_liga_a_ia():
    from py_photos_organize_tpv.main import criar_parser
    args = criar_parser().parse_args(["--com-ia"])
    assert args.com_ia is True


def test_sem_ia_continua_valido():
    """Quem já escrevia --sem-ia não pode ser quebrado; agora é redundante."""
    from py_photos_organize_tpv.main import criar_parser
    args = criar_parser().parse_args(["--sem-ia"])
    assert args.com_ia is False


def test_com_ia_e_sem_ia_juntos_sao_recusados():
    """A intenção fica ambígua: melhor falhar do que adivinhar."""
    from py_photos_organize_tpv.main import criar_parser
    with pytest.raises(SystemExit):
        criar_parser().parse_args(["--com-ia", "--sem-ia"])


# ------------- o relatório de classificação acompanha a mídia (não órfão)

def _com_sidecar(pasta, nome, texto="praia\n====\nINDICE: 2/5\n"):
    """Cria uma mídia e o relatório de classificação ao lado dela."""
    from PIL import Image as _Image
    midia = pasta / nome
    _Image.new("RGB", (32, 32), (4, 4, 4)).save(midia)
    (pasta / (nome + ".gemini_36_flash.md")).write_text(texto, encoding="utf-8")
    return midia


def test_relatorio_acompanha_a_midia_ao_copiar(tmp_path):
    """Separar a classificação da foto joga fora o que custou dinheiro de API."""
    origem = tmp_path / "origem"
    origem.mkdir()
    _com_sidecar(origem, "2019_07_04_08h09m10s-foto.jpg")
    destino = tmp_path / "destino"

    organizar(_config(origem, destino))

    copiadas = list(destino.rglob("*.jpg"))
    assert len(copiadas) == 1
    relatorio = copiadas[0].with_name(copiadas[0].name + ".gemini_36_flash.md")
    assert relatorio.is_file(), "o relatório ficou para trás"
    assert "INDICE: 2/5" in relatorio.read_text(encoding="utf-8")


def test_relatorio_acompanha_a_midia_ao_mover(tmp_path):
    origem = tmp_path / "origem"
    origem.mkdir()
    _com_sidecar(origem, "2019_07_04_08h09m10s-foto.jpg")
    destino = tmp_path / "destino"

    organizar(_config(origem, destino, mover=True))

    movidas = list(destino.rglob("*.jpg"))
    assert len(movidas) == 1
    assert movidas[0].with_name(movidas[0].name + ".gemini_36_flash.md").is_file()
    # A mídia saiu da origem; o relatório não pode ter ficado órfão lá.
    assert not list(origem.glob("*.gemini_36_flash.md")), "relatório órfão na origem"


def test_midia_sem_relatorio_continua_funcionando(tmp_path):
    """A maioria dos arquivos não tem relatório: nada pode quebrar por isso."""
    origem = tmp_path / "origem"
    origem.mkdir()
    Image.new("RGB", (32, 32), (5, 5, 5)).save(origem / "2019_07_04_08h09m10s-s.jpg")
    destino = tmp_path / "destino"
    estats = organizar(_config(origem, destino))
    assert estats.copiados == 1
    assert estats.erros == 0
