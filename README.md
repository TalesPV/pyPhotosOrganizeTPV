# pyPhotosOrganizeTPV
Organiza fotos, vídeos e outros formatos em subpastas por data (EXIF/metadados,
nome do arquivo ou sistema de arquivos), gerando arquivos no formato:

```
{data1}-{data2}-{cidade}-{titulo}{ext}
```

- `data1` é a data mais antiga e `data2` a mais recente (se houver uma só,
  ela se repete nos dois blocos), com máscara `YYYY_MM_DD_HHhMMmSSs`.
- `cidade` vem do GPS dos metadados (EXIF/XMP de imagens e localização
  ISO 6709/©xyz de vídeos via ffmpeg) resolvido pelo Nominatim/OpenStreetMap
  com cache local; sem GPS usa `sem_gps`.
- `titulo` é um título em snake_case de até 5 palavras, gerado por IA
  (GPT-4o mini para imagens e Gemini para vídeos, com fallback cruzado).
  Resultados são cacheados por SHA-256.

### Fontes de metadados por tipo de arquivo

A extração de metadados é feita pelo pacote compartilhado
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
**desativada (`--sem-ia`) ou indisponível por qualquer motivo** (sem chave,
sem conectividade, falha nas chamadas), o programa continua funcionando
normalmente e gera os arquivos **sem o bloco de título**:

```
{data1}-{data2}-{cidade}{ext}
```

ex.: `2023_05_10_14h30m00s-2023_05_10_14h30m00s-sem_gps.jpg`

Falhas de IA não são cacheadas, então uma execução futura com IA disponível
pode gerar os títulos normalmente.

## Requisitos
- [uv](https://docs.astral.sh/uv/)
- Python >= 3.14 (o uv gerencia a instalação)

## Instalação
```bash
uv sync
```

## Como executar

O script é executado pelo módulo Python `py_photos_organize_tpv`, via `uv run`:

```bash
uv run python -m py_photos_organize_tpv [opções]
```

O comando mínimo exige apenas a pasta de origem (`-o`) e a de destino (`-d`):

```bash
uv run python -m py_photos_organize_tpv -o D:\fotos -d E:\organizado
```

### Recomendação: comece com um dry-run

O `--dry-run` mostra exatamente o que seria feito (copiar/mover e os novos
nomes) **sem alterar nada no disco**. Confira a saída antes de executar de
verdade:

```bash
uv run python -m py_photos_organize_tpv -o D:\fotos -d E:\organizado --dry-run
```

Depois de conferir, execute sem a flag para aplicar:

```bash
uv run python -m py_photos_organize_tpv -o D:\fotos -d E:\organizado
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
| `--sem-ia` | desativa as APIs de IA (sem consumo de tokens/créditos); arquivos sem o bloco de título | desativado |
| `--chave-gemini` | arquivo com a chave da API Gemini | `._SECRETS/._CHAVE_GEMINI.key` |
| `--chave-openai` | arquivo com a chave da API OpenAI | `._SECRETS/._CHAVE_OPENAI_CHATGPT.key` |
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

### Rodar sem IA (mais rápido e sem custo; nomes sem o bloco de título)

```bash
uv run python -m py_photos_organize_tpv -o D:\fotos -d E:\organizado --sem-ia
```

Se a IA falhar durante a execução (chave inválida, sem internet etc.), o
comportamento é o mesmo do `--sem-ia`: o processamento continua e os arquivos
são gerados como `{data1}-{data2}-{cidade}{ext}`.

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

## Chaves de API
As chaves ficam em `._SECRETS/._CHAVE_GEMINI.key` e
`._SECRETS/._CHAVE_OPENAI_CHATGPT.key` (ignoradas pelo git). Os títulos
gerados por IA são cacheados por SHA-256 em `cache_sha256_titulos.jsonl`
e as cidades do GPS em `cache_gps_cidades.json` (ambos ignorados pelo git).

## Metadados: bibliotecas e critérios

A extração de metadados (datas e GPS de fotos, vídeos e áudios) vive no
pacote compartilhado [`pereiras-common`](https://github.com/TalesPV/pereiras-scripts),
consumido via `uv sync`:

```
pereiras-common @ git+https://github.com/TalesPV/pereiras-scripts.git@main
```

- **Pillow** (+ pillow-heif): padrão de fato para imagens (EXIF + XMP).
- **ffmpeg** (via imageio-ffmpeg): padrão de fato para vídeo/áudio; binário empacotado.
- **mutagen**: padrão para metadados de áudio (ID3, MP4, comentários Vorbis).
- **piexif/exifread**: fallbacks para EXIF parcialmente corrompido ou não padronizado.
- **defusedxml**: parser XML protegido contra XXE/billion laughs (leitura segura de XMP).
- **exiftool** (binário externo, opcional): padrão-ouro em perícia forense.

Critérios de decisão: manutenção ativa, reputação na comunidade, histórico de
segurança e menor superfície de dependências. Parsers de metadados são
superfície de ataque ao processar arquivos não confiáveis — por isso evita-se
bibliotecas abandonadas e wrappers que injetam nomes de arquivo em linha de
comando. A integração com exiftool é opcional (sem dependência nova) e
recomendada apenas para quem mantém o binário atualizado.

## Testes
```bash
uv run pytest
```
