# pyPhotosOrganizeTPV

Organiza fotos, vídeos e áudios em subpastas por data (EXIF/metadados,
nome do arquivo ou sistema de arquivos), gerando arquivos no formato:

```
{data1}-{data2}-{cidade}-{titulo}-{hash6}{ext}
```

- `data1` é a data mais antiga e `data2` a mais recente (se houver uma só,
  ela se repete nos dois blocos), com máscara `YYYY_MM_DD_HHhMMmSSs`.
- `cidade` vem do GPS dos metadados resolvido pelo Nominatim/OpenStreetMap
  com cache local; sem GPS usa `sem_gps`; sem resposta do serviço, usa as
  coordenadas (`-23_5500_-46_6333`).
- `titulo` é um título em snake_case de até 5 palavras, gerado por IA
  (GPT-4o mini primário para imagens e Gemini para vídeos, com fallback
  cruzado). Resultados são cacheados por SHA-256.
- `hash6` é o hash alfanumérico de 6 caracteres do conteúdo do arquivo
  (função `hash_curto_6` do pacote compartilhado `pereiras-common`):
  identifica o arquivo e evita nomes duplicados quando há cópias do
  mesmo conteúdo na origem.

---

## Índice

1. [Visão geral e especificação](#visão-geral-e-especificação)
2. [Arquitetura e relacionamento entre os módulos](#arquitetura-e-relacionamento-entre-os-módulos)
3. [Requisitos e instalação](#requisitos-e-instalação)
4. [Chaves de IA (segurança)](#chaves-de-ia-segurança)
5. [Como executar](#como-executar)
6. [Parâmetros](#parâmetros)
7. [Exemplos](#exemplos)
8. [Testes (TDD)](#testes-tdd)
9. [Pull Requests](#pull-requests)
10. [ToDos](#todos)

---

## Visão geral e especificação

Fluxo de cada arquivo encontrado na pasta de origem:

1. **Extensão**: só arquivos suportados (imagens, vídeos, áudios,
   office e outros listados em `pereiras_common.metadados`).
2. **Datas e GPS**: metadados embutidos (EXIF/XMP/PNG, ffmpeg/mutagen),
   depois nome do arquivo, depois sistema de arquivos; exiftool é
   fallback opcional.
3. **Sufixo de pasta**: `videos`, `audios`, `office`, `outros_tipos`,
   `screen_capture`, `social_media`, `instant_messages`,
   `low_resolution` (conforme extensão/nome/tamanho).
4. **Nome alvo**: título por IA (se habilitada), cidade por GPS e
   hash curto do conteúdo.
5. **Ação**: copiar (padrão) ou mover; se o alvo já existir:
   duplicar (`_2`, `_3`, ...), ignorar ou sobrescrever.

### Fontes de metadados por tipo de arquivo

A extração é feita pelo pacote compartilhado
[`pereiras-common`](https://github.com/TalesPV/pereiras-scripts)
(módulo `pereiras_common.metadados`):

| Tipo | Data | GPS |
| --- | --- | --- |
| Imagem (JPEG/PNG/WebP/TIFF/HEIC...) | EXIF (`DateTimeOriginal`, `DateTimeDigitized`, `DateTime`), XMP (`CreateDate`, `DateCreated`, `DateTimeOriginal`), texto PNG (`Creation Time`, `date:create`) | EXIF (IFD GPS 0x8825), XMP (`GPSLatitude`/`GPSLongitude`), fallbacks piexif/exifread |
| Vídeo (MP4/MOV/...) | `creation_time` via ffmpeg; fallback ©day (mutagen) | `location` / `©xyz` (ISO 6709) via ffmpeg; fallback ©xyz (mutagen) |
| Áudio (MP3/M4A/OGG/Flac...) | ID3 `TDRC`/`TDOR`/`TYER`, ©day, comentários Vorbis (mutagen) | ©xyz (MP4/M4A) |
| Fallback opcional | binário **exiftool**, se instalado (padrão forense) | idem |
| Última alternativa | sistema de arquivos (min criação/modificação) | — |

### Resiliência sem IA

O `{titulo}` é a única parte do nome definida por IA. Se a IA estiver
**desativada (`--sem-ia`) ou indisponível por qualquer motivo** (sem
chave, sem conectividade, falha nas chamadas), o programa continua
funcionando e gera os arquivos **sem o bloco de título**:

```
{data1}-{data2}-{cidade}-{hash6}{ext}
```

ex.: `2023_05_10_14h30m00s-2023_05_10_14h30m00s-sem_gps-k3x9ab.jpg`

Falhas de IA não são cacheadas, então uma execução futura com IA
disponível pode gerar os títulos normalmente.

## Arquitetura e relacionamento entre os módulos

```
py_photos_organize_tpv/
├── __main__.py        # permite executar com "python -m py_photos_organize_tpv"
├── main.py            # CLI: argparse, log e montagem da Config
├── organizador.py     # núcleo: varredura, datas, nome alvo, copiar/mover
├── nomeacao.py        # monta/extrai datas e monta o nome alvo
├── geolocalizacao.py  # cidade por GPS (Nominatim + cache local)
└── ia.py              # títulos por IA (usa pereiras_common.ia p/ fotos)
```

Relacionamentos:

```
main.py ──> organizador.py ──> ia.py ──────────> pereiras_common.ia (fotos)
                        │         └──────────> APIs Gemini/OpenAI (vídeos)
                        ├──> geolocalizacao.py
                        ├──> nomeacao.py ────> pereiras_common.uteis (snake_case)
                        └──> pereiras_common.metadados / pereiras_common.uteis
```

## Requisitos e instalação

- [uv](https://docs.astral.sh/uv/) (gerencia Python e dependências)
- Python >= 3.14 (o uv instala automaticamente)

```bash
uv sync
```

Dependência principal: `pereiras-common` (via git, ver
[pereiras-scripts](https://github.com/TalesPV/pereiras-scripts)).

## Chaves de IA (segurança)

As chaves de API ficam **fora do repositório**, na pasta do usuário:

```
~/.chaves_ia/chave_gemini.key            (Gemini)
~/.chaves_ia/chave_openai_chatgpt.key    (OpenAI)
```

- Nunca versionar chaves no git (a pasta `~/.chaves_ia` está fora do projeto).
- Trocar o local pela linha de comando: `--chave-gemini C:\meu\caminho.key`
  e `--chave-openai C:\meu\caminho.key`.
- O programa lê o conteúdo do arquivo; a chave nunca aparece em logs.

## Como executar

```bash
uv run python -m py_photos_organize_tpv [opções]
```

O comando mínimo exige a pasta de origem (`-o`) e a de destino (`-d`):

```bash
uv run python -m py_photos_organize_tpv -o D:\fotos -d E:\organizado
```

### Recomendação: comece com um dry-run

O `--dry-run` mostra exatamente o que seria feito (copiar/mover e os
novos nomes) **sem alterar nada no disco**:

```bash
uv run python -m py_photos_organize_tpv -o D:\fotos -d E:\organizado --dry-run
```

Cada execução grava um log em `logs/log_py_photos_organize_tpv_<data>.log`.

## Parâmetros

| Opção | Descrição | Padrão |
| --- | --- | --- |
| `-o, --files-orign` | pasta de origem a percorrer (recursivo) | `d:\` |
| `-d, --files-destination` | pasta de destino | `E:\TMP-fotos` |
| `-f, --folders` | máscara strftime das subpastas de data | `%Y_%m` |
| `-w, --overwrite` | `d` duplicar, `i` ignorar, `o` sobrescrever | `d` |
| `-q, --batch-quantity-files` | processa no máximo N arquivos (`0` = todos) | `0` |
| `-y, --min-year-discart-date` | ignora datas anteriores a este ano | `1980` |
| `-s, --min-size-escape-low-resolution` | sufixo `low_resolution` abaixo deste tamanho (bytes) | `100000` |
| `-g, --generate-folder-sufix` | sufixo de pasta por origem (`videos`, `social_media`, ...) | ativado |
| `-n, --rename-file` | renomeia para o formato alvo | ativado |
| `-l, --timestamp-log` | nome do arquivo de log com timestamp | ativado |
| `--sem-ia` | desativa as APIs de IA; arquivos sem o bloco de título | desativado |
| `--chave-gemini` | arquivo com a chave da API Gemini | `~/.chaves_ia/chave_gemini.key` |
| `--chave-openai` | arquivo com a chave da API OpenAI | `~/.chaves_ia/chave_openai_chatgpt.key` |
| `--dry-run` | apenas mostra o que seria feito, sem alterar nada | desativado |
| `--mover` | move os arquivos em vez de copiá-los | desativado |
| `--frames` | frames extraídos por vídeo para a IA | `5` |

As flags booleanas aceitam a forma negativa, ex.: `--no-generate-folder-sufix`,
`--no-rename-file`, `--no-timestamp-log`.

## Exemplos

### Organizar uma pasta completa (modo padrão: copia)

```bash
uv run python -m py_photos_organize_tpv -o D:\fotos -d E:\organizado
```

### Testar com um lote pequeno (10 arquivos) antes de rodar tudo

```bash
uv run python -m py_photos_organize_tpv -o D:\fotos -d E:\organizado -q 10 --dry-run
```

### Mover (em vez de copiar) mantendo pasta por ano/mês

```bash
uv run python -m py_photos_organize_tpv -o D:\fotos -d E:\organizado --mover
```

### Agrupar por ano/mês/dia e sem sufixo de origem

```bash
uv run python -m py_photos_organize_tpv -o D:\fotos -d E:\organizado -f "%Y_%m_%d" --no-generate-folder-sufix
```

### Controlar o que acontece com arquivos que já existem no destino

```bash
# Duplicar com sufixo _2, _3, ... (padrão)
uv run python -m py_photos_organize_tpv -o D:\fotos -d E:\organizado -w d

# Ignorar quem já existe no destino
uv run python -m py_photos_organize_tpv -o D:\fotos -d E:\organizado -w i

# Sobrescrever o arquivo do destino
uv run python -m py_photos_organize_tpv -o D:\fotos -d E:\organizado -w o
```

### Organizar sem IA (sem consumo de tokens/créditos)

```bash
uv run python -m py_photos_organize_tpv -o D:\fotos -d E:\organizado --sem-ia
```

### Ajustar regras de data e resolução

```bash
# Ignorar arquivos com data anterior a 2000 e marcar low_resolution abaixo de 50 kB
uv run python -m py_photos_organize_tpv -o D:\fotos -d E:\organizado -y 2000 -s 50000
```

### Manter o nome original, apenas reorganizando as pastas

```bash
uv run python -m py_photos_organize_tpv -o D:\fotos -d E:\organizado --no-rename-file
```

### Usar arquivos de chave de IA em outro local

```bash
uv run python -m py_photos_organize_tpv -o D:\fotos -d E:\organizado --chave-gemini C:\chaves\gemini.key --chave-openai C:\chaves\openai.key
```

## Testes (TDD)

```bash
uv run pytest
```

- `tests/test_nomeacao.py`: datas, snake_case e montagem do nome alvo.
- `tests/test_organizador.py`: integração (varredura, sufixos, destino,
  dedup de nomes, dry-run, títulos/cache de IA com dublês).
- Os testes de metadados vivem no pacote `pereiras-common`
  (fonte única das funções).

## Pull Requests

1. Crie uma branch a partir de `main`: `git switch -c feat/nome-curto`.
2. Ajuste os testes primeiro (TDD) e rode `uv run pytest`.
3. Atualize este README se o formato de nome, parâmetros ou fluxo mudarem.
4. Abra o PR para `main` descrevendo: problema, solução, testes e impactos.

## ToDos

- [ ] Migrar as funções de data/nomeação duplicadas para `pereiras-common`
      (`extrair_data_nome`, `montar_dt`, `parsear_data_exif`...).
- [ ] Usar `analisar_foto` (pereiras_common.ia) também para vídeos quando
      houver suporte a frames no pacote compartilhado.
- [ ] Opção de usar o nível de legalidade da análise para alertar arquivos
      de nível 3+ durante a organização.
- [ ] CI (GitHub Actions) rodando os testes a cada PR.
