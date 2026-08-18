# pyPhotosOrganizeTPV

Organiza fotos, vídeos e áudios em subpastas por data (EXIF/metadados,
nome do arquivo ou sistema de arquivos), gerando as mídias no formato
padrão do pacote compartilhado:

```
YYYY_MM_DD_HHhMMmSSs-YYYY_MM_DD_HHhMMmSSs-cidade-hash6-titulo.ext
```

- 1º bloco = data mais antiga; 2º = mais recente (repetida se houver uma só).
- `cidade` vem do GPS dos metadados resolvido pelo Nominatim/OpenStreetMap
  com cache local; sem GPS usa `sem_gps`; sem resposta do serviço, usa as
  coordenadas (`-23_5500_-46_6333`).
- `hash6` é o hash alfanumérico de 6 caracteres do **conteúdo** do arquivo
  (função `hash_curto_6` do pacote `pereiras-common`). Fica ANTES do
  título: arquivos diferentes do mesmo horário não se sobrescrevem.
- `titulo` é um título em snake_case de até 5 palavras, gerado por IA
  (GPT-4o mini primário para imagens e Gemini para vídeos, com fallback
  cruzado). Resultados são cacheados por SHA-256.
- Apenas **mídias** (foto/vídeo/áudio) são renomeadas; os demais arquivos
  (office, PDFs, textos...) mantêm o nome original.
- O relatório de classificação (`.gemini_36_flash.md`) gerado pelo
  `verificar_fotos_videos` **acompanha a mídia** ao copiar ou mover: separá-los
  deixaria órfã uma análise que custou dinheiro de API.

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
2. **Datas e GPS**: `pereiras_common.metadados.obter_datas` — metadados
   embutidos (EXIF/XMP/PNG, ffmpeg/mutagen), depois nome do arquivo,
   depois sistema de arquivos; exiftool é fallback opcional.
3. **Sufixo de pasta**: `pereiras_common.metadados.classificar_sufixo` —
   `videos`, `audios`, `office`, `outros_tipos`, `screen_capture`,
   `social_media`, `instant_messages`, `low_resolution`.
4. **Nome alvo**: apenas para MÍDIAS — título por IA (se habilitada),
   cidade por GPS e hash curto do conteúdo, montados por
   `pereiras_common.nomeacao.montar_nome_midia`. Arquivos que não são
   mídia mantêm o nome original.
5. **Ação**: copiar (padrão) ou mover; se o alvo já existir:
   duplicar (`_2`, `_3`, ...), ignorar ou sobrescrever.

### Fontes de metadados por tipo de arquivo

A extração é feita pelo pacote compartilhado
[`pereiras-common`](https://github.com/TalesPV/pereiras-scripts)
(módulo `pereiras_common.metadados`):

| Tipo | Data | GPS |
| --- | --- | --- |
| Imagem (JPEG/PNG/WebP/TIFF/HEIC...) | EXIF do IFD0 **e do sub-IFD 0x8769** (`DateTimeOriginal`, `DateTimeDigitized`, `DateTime`), XMP (`CreateDate`, `DateCreated`, `DateTimeOriginal`), texto PNG (`Creation Time`, `date:create`) | EXIF (IFD GPS 0x8825), XMP (`GPSLatitude`/`GPSLongitude`), fallbacks piexif/exifread (só em JPEG/TIFF/HEIC) |
| Vídeo (MP4/MOV/...) | `creation_time` via ffmpeg; fallback ©day (mutagen) | `location` / `©xyz` (ISO 6709) via ffmpeg; fallback ©xyz (mutagen) |
| Áudio (MP3/M4A/OGG/Flac...) | ID3 `TDRC`/`TDOR`/`TYER`, ©day, comentários Vorbis (mutagen) | ©xyz (MP4/M4A) |
| Fallback opcional | binário **exiftool**, se instalado (padrão forense) | idem |
| Última alternativa | sistema de arquivos (min criação/modificação) | — |

### Resiliência sem IA

O `{titulo}` é a única parte do nome definida por IA. Se a IA estiver
**desativada (`--sem-ia`) ou indisponível por qualquer motivo** (sem
chave, sem conectividade, falha nas chamadas), o programa continua
funcionando e gera as mídias **sem o bloco de título** (o hash permanece):

```
YYYY_MM_DD_HHhMMmSSs-YYYY_MM_DD_HHhMMmSSs-cidade-hash6.ext
```

ex.: `2023_05_10_14h30m00s-2023_05_10_14h30m00s-sem_gps-k3x9ab.jpg`

Falhas de IA não são cacheadas, então uma execução futura com IA
disponível pode gerar os títulos normalmente.

**O título já gravado no nome nunca é perdido.** Se o arquivo já se chama
`…-cidade-hash6-titulo.ext` (ou o formato antigo `…-cidade-titulo.ext`) e
não há título novo, o programa **mantém o nome original** e registra
`TÍTULO PRESERVADO` no log — renomear apagaria uma informação que só uma
nova chamada de IA saberia recriar. Arquivos sem título continuam sendo
renomeados normalmente (ganham o bloco `hash6`).

## Arquitetura e relacionamento entre os módulos

```
py_photos_organize_tpv/
├── __main__.py        # permite executar com "python -m py_photos_organize_tpv"
├── main.py            # CLI: argparse, log e montagem da Config
├── organizador.py     # núcleo: varredura, datas, nome alvo, copiar/mover
└── ia.py              # títulos por IA (usa pereiras_common.ia p/ fotos)
```

Funções comuns vivem no pacote
[`pereiras-common`](https://github.com/TalesPV/pereiras-scripts):

```
main.py ──> organizador.py ──> ia.py ──────────────────> pereiras_common.ia (fotos)
                        │         └────────────────────> APIs Gemini/OpenAI (vídeos)
                        ├──> pereiras_common.metadados  (obter_datas, classificar_sufixo)
                        ├──> pereiras_common.nomeacao   (montar_nome_midia, pastas, datas)
                        ├──> pereiras_common.geolocalizacao (cidade por GPS)
                        └──> pereiras_common.uteis      (hash_curto_6, chaves)
```

## Requisitos e instalação

- [uv](https://docs.astral.sh/uv/) (gerencia Python e dependências)
- Python >= 3.14 (o uv instala automaticamente)

```bash
uv sync
```

Dependência principal: `pereiras-common` (via git, ver
[pereiras-scripts](https://github.com/TalesPV/pereiras-scripts)).

### exiftool (opcional, recomendado)

O [exiftool](https://exiftool.org/) é o padrão de referência em leitura de
metadados e serve de **fallback** quando Pillow, ffmpeg e mutagen não acham
data ou GPS. Sem ele o programa funciona, apenas com menos alternativas.

```powershell
winget install --id OliverBetz.ExifTool --exact
```

O caminho é resolvido no momento do `import`: depois de instalar, abra um
terminal novo para que o programa o enxergue.


## Chaves de IA (segurança)

As chaves de API ficam **fora do repositório**, na pasta do usuário
(`$HOME\.chaves_ia\` no Windows; `~/.chaves_ia/` no Linux/macOS):

```
$HOME\.chaves_ia\chave_google_gemini.key     (Gemini)
$HOME\.chaves_ia\chave_openai_chatgpt.key    (OpenAI)
```

- Nunca versionar chaves no git (a pasta `$HOME.chaves_ia` está fora do projeto).
- Trocar o local pela linha de comando: `--chave-gemini C:\meu\caminho.key`
  e `--chave-openai C:\meu\caminho.key`.
- Os caminhos (chaves, `-o` e `-d`) aceitam `~`, `$HOME` e `%USERPROFILE%`.
  No PowerShell, entre **aspas simples** o `$HOME` não é expandido pelo
  shell — o programa resolve mesmo assim.
- O programa lê o conteúdo do arquivo; a chave nunca aparece em logs.

## Como executar

```bash
uv run python -m py_photos_organize_tpv [opções]
```

O comando mínimo exige a pasta de origem (`-o`) e a de destino (`-d`):

```bash
uv run python -m py_photos_organize_tpv -o D:\fotos -d E:\organizado
```

### Atenção: destino dentro da origem

Se a pasta de destino estiver **dentro** da pasta de origem (inclusive
quando `-o` e `-d` são a mesma pasta), o programa emite um aviso no log:
ao copiar, a coleção é duplicada e uma execução seguinte varreria também
as cópias. Prefira um destino fora da origem, ou use `--mover`.

### Simula por padrão; `--aplicar` executa

Os três programas do conjunto seguem a mesma regra: **nada é alterado sem
`--aplicar`**. Sem a flag, o programa mostra exatamente o que faria
(copiar/mover e os novos nomes) sem tocar no disco.

```bash
# simula (padrão)
uv run python -m py_photos_organize_tpv -o D:\fotos -d E:\organizado

# executa de verdade
uv run python -m py_photos_organize_tpv -o D:\fotos -d E:\organizado --aplicar
```

`--dry-run` continua sendo aceito para não quebrar scripts antigos — hoje
é redundante, porque simular virou o padrão.

Cada execução grava um log em `logs/log_py_photos_organize_tpv_<data>.log`.

## Parâmetros

| Opção | Descrição | Padrão |
| --- | --- | --- |
| `-o, --files-orign` | pasta de origem a percorrer (recursivo) | `d:\` |
| `-d, --files-destination` | pasta de destino | `E:\TMP-fotos` |
| `-f, --folders` | máscara strftime das subpastas de data | `%Y_%m` |
| `-w, --overwrite` | `d` duplicar, `i` ignorar, `o` sobrescrever | `d` |
| `-q, --batch-quantity-files` | processa no máximo N arquivos (`0` = todos) | `0` |
| `-y, --min-year-discart-date` | ignora datas anteriores a este ano (mesmo valor nos três programas) | `1980` |
| `-s, --min-size-escape-low-resolution` | sufixo `low_resolution` abaixo deste tamanho (bytes) | `100000` |
| `-g, --generate-folder-sufix` | sufixo de pasta por origem (`videos`, `social_media`, ...) | ativado |
| `-n, --rename-file` | renomeia para o formato alvo | ativado |
| `-l, --timestamp-log` | nome do arquivo de log com timestamp | ativado |
| `--com-ia` | **gera títulos com IA** (consome tokens e créditos) | desativado |
| `--sem-ia` | explicita que não se deve usar IA (já é o padrão) | — |
| `--chave-gemini` | arquivo com a chave da API Gemini | `$HOME\.chaves_ia\chave_google_gemini.key` |
| `--chave-openai` | arquivo com a chave da API OpenAI | `$HOME\.chaves_ia\chave_openai_chatgpt.key` |
| `--aplicar` | executa as alterações (sem ele, apenas simula) | desativado |
| `--mover` | move os arquivos em vez de copiá-los | desativado |
| `--frames` | frames extraídos por vídeo para a IA | `5` |

As flags booleanas aceitam a forma negativa, ex.: `--no-generate-folder-sufix`,
`--no-rename-file`, `--no-timestamp-log`.

## Exemplos

### Organizar uma pasta completa (modo padrão: copia)

```bash
uv run python -m py_photos_organize_tpv -o D:\fotos -d E:\organizado --aplicar
```

### Testar com um lote pequeno (10 arquivos) antes de rodar tudo

Sem `--aplicar` já é simulação:

```bash
uv run python -m py_photos_organize_tpv -o D:\fotos -d E:\organizado -q 10
```

### Mover (em vez de copiar) mantendo pasta por ano/mês

```bash
uv run python -m py_photos_organize_tpv -o D:\fotos -d E:\organizado --aplicar --mover
```

### Agrupar por ano/mês/dia e sem sufixo de origem

```bash
uv run python -m py_photos_organize_tpv -o D:\fotos -d E:\organizado --aplicar -f "%Y_%m_%d" --no-generate-folder-sufix
```

### Controlar o que acontece com arquivos que já existem no destino

```bash
# Duplicar com sufixo _2, _3, ... (padrão)
uv run python -m py_photos_organize_tpv -o D:\fotos -d E:\organizado --aplicar -w d

# Ignorar quem já existe no destino
uv run python -m py_photos_organize_tpv -o D:\fotos -d E:\organizado --aplicar -w i

# Sobrescrever o arquivo do destino
uv run python -m py_photos_organize_tpv -o D:\fotos -d E:\organizado --aplicar -w o
```

### IA é opt-in

Sem `--com-ia` **nenhuma API é chamada** e os arquivos saem sem o bloco de
título. As duas opções são mutuamente exclusivas: usar `--com-ia --sem-ia`
junto é recusado, porque a intenção fica ambígua.

Um título já gravado no nome nunca é perdido nesse modo (ver
[resiliência sem IA](#resiliência-sem-ia)).

### Organizar sem IA (padrão)

```bash
uv run python -m py_photos_organize_tpv -o D:\fotos -d E:\organizado --aplicar --sem-ia
```

### Ajustar regras de data e resolução

```bash
# Ignorar arquivos com data anterior a 2000 e marcar low_resolution abaixo de 50 kB
uv run python -m py_photos_organize_tpv -o D:\fotos -d E:\organizado --aplicar -y 2000 -s 50000
```

### Manter o nome original, apenas reorganizando as pastas

```bash
uv run python -m py_photos_organize_tpv -o D:\fotos -d E:\organizado --aplicar --no-rename-file
```

### Usar arquivos de chave de IA em outro local

```bash
uv run python -m py_photos_organize_tpv -o D:\fotos -d E:\organizado --aplicar --chave-gemini C:\chaves\gemini.key --chave-openai C:\chaves\openai.key
```

## Dados gerados x código versionado

Nada do que o programa produz entra no git — **cada ambiente gera o seu**:
`cache_sha256_titulos.jsonl` (títulos já gerados por IA),
`cache_gps_cidades.json` (geocodificação) e `logs/`.

Ao clonar o repositório é esperado que nenhum deles exista: aparecem na
primeira execução. Versioná-los daria conflito a cada rodada e colocaria
caminhos de arquivos pessoais dentro do repositório. As regras do
`.gitignore` são por padrão (`cache_*.jsonl`) e não por nome exato.

## Testes (TDD)

```bash
uv run pytest
```

- `tests/test_organizador.py`: 25 testes de integração (varredura, sufixos,
  destino, dedup de nomes, dry-run — inclusive o resumo de `--mover` —,
  aviso de destino dentro da origem, leitura única do SHA-256 por arquivo,
  títulos/cache de IA com dublês e regra de "outros arquivos não renomeados").
- Os testes de nomeação, metadados, geolocalização, hash e IA vivem no
  pacote `pereiras-common` (fonte única das funções).

## Pull Requests

1. Crie uma branch a partir de `main`: `git switch -c feat/nome-curto`.
2. Ajuste os testes primeiro (TDD) e rode `uv run pytest`.
3. Atualize este README se o formato de nome, parâmetros ou fluxo mudarem.
4. Abra o PR para `main` descrevendo: problema, solução, testes e impactos.

## ToDos

- [ ] Usar `analisar_foto` (pereiras_common.ia) também para vídeos quando
      houver suporte a frames no pacote compartilhado.
- [x] Migrar `sha256_arquivo` e o cache de títulos para `pereiras-common`
      (reaproveitamento no verificar_fotos_videos). **Feito** — o módulo
      `ia.py` agora delega a `pereiras_common.uteis`.
- [ ] Opção de usar o nível de legalidade da análise para alertar arquivos
      de nível 3+ durante a organização.
- [ ] CI (GitHub Actions) rodando os testes a cada PR.
