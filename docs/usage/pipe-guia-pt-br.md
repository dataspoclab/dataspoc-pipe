# Guia de Uso — DataSpoc Pipe

## Sumario

1. [Introducao](#1-introducao)
2. [Instalacao](#2-instalacao)
3. [Quickstart](#3-quickstart)
4. [Configuracao](#4-configuracao)
5. [Comandos](#5-comandos)
6. [Extracao incremental](#6-extracao-incremental)
7. [Multi-cloud](#7-multi-cloud)
8. [Convencao de diretorios](#8-convencao-de-diretorios)
9. [Transforms](#9-transforms)
10. [Agendamento](#10-agendamento)
11. [Troubleshooting](#11-troubleshooting)
12. [Exemplos praticos](#12-exemplos-praticos)

---

## 1. Introducao

### O que e o DataSpoc Pipe

DataSpoc Pipe e um motor de ingestao de dados que transforma qualquer fonte de dados em arquivos Parquet organizados em um bucket (local ou na nuvem). Ele utiliza o protocolo Singer para extrair dados e automatiza todo o fluxo de conversao, particionamento e armazenamento.

O fluxo e simples:

```
[Fonte de Dados] --> [Singer Tap] --> stdout --> [DataSpoc Pipe] --> Parquet --> [Bucket]
```

### Para quem e

- Engenheiros de dados que precisam de um pipeline de ingestao leve e sem dependencias pesadas.
- Times que querem montar um data lake sem precisar de infraestrutura complexa.
- Desenvolvedores que ja conhecem o ecossistema Singer e querem um destino Parquet padronizado.

### O que resolve

- Elimina a necessidade de escrever codigo para converter JSON do Singer em Parquet.
- Padroniza a estrutura de diretorios no bucket, criando um contrato estavel entre ingestao e consumo.
- Gerencia estado incremental automaticamente (bookmarks).
- Funciona com qualquer provedor de nuvem (S3, GCS, Azure) ou sistema de arquivos local.

### Parte da plataforma DataSpoc

O DataSpoc Pipe e a camada de ingestao da plataforma DataSpoc:

- **DataSpoc Pipe** (este projeto) — Ingestao: Singer -> Parquet -> Bucket
- **DataSpoc Lens** — Warehouse virtual: SQL + Jupyter + IA sobre seu lake
- **DataSpoc ML** — AutoML: treina modelos direto do lake

O bucket e o contrato entre os tres produtos. O Pipe escreve. O Lens le. O ML consome e produz.

---

## 2. Instalacao

### Requisitos

- Python 3.10 ou superior
- pip (gerenciador de pacotes Python)

### Instalacao basica

```bash
pip install dataspoc-pipe
```

### Instalacao com extras para nuvem

Dependendo do provedor de armazenamento que voce vai usar, instale o extra correspondente:

```bash
# Para AWS S3
pip install dataspoc-pipe[s3]

# Para Google Cloud Storage
pip install dataspoc-pipe[gcs]

# Para Azure Blob Storage
pip install dataspoc-pipe[azure]

# Para multiplos provedores ao mesmo tempo
pip install dataspoc-pipe[s3,gcs]
```

### Verificando a instalacao

```bash
dataspoc-pipe --version
```

---

## 3. Quickstart

Crie seu primeiro pipeline em 15 minutos usando `tap-csv` como fonte de dados.

### Passo 1: Prepare um arquivo CSV de exemplo

Crie um arquivo CSV para servir de fonte:

```bash
mkdir -p /tmp/dados

cat > /tmp/dados/clientes.csv << 'EOF'
id,nome,email,cidade
1,Ana Silva,ana@exemplo.com,Sao Paulo
2,Bruno Costa,bruno@exemplo.com,Rio de Janeiro
3,Carla Souza,carla@exemplo.com,Belo Horizonte
4,Diego Lima,diego@exemplo.com,Curitiba
5,Eva Santos,eva@exemplo.com,Porto Alegre
EOF
```

### Passo 2: Instale o tap-csv

```bash
pip install tap-csv
```

### Passo 3: Inicialize o DataSpoc Pipe

```bash
dataspoc-pipe init
```

Isso cria a estrutura de configuracao em `~/.dataspoc-pipe/`:

```
~/.dataspoc-pipe/
  config.yaml          # Configuracao global
  pipelines/           # Diretorio dos pipelines
```

### Passo 4: Crie o pipeline

Voce pode usar o wizard interativo:

```bash
dataspoc-pipe add meu-pipeline
```

O wizard vai perguntar:
- Tap Singer: `tap-csv`
- Config do tap: o JSON de configuracao ou caminho para um arquivo
- Bucket de destino: `file:///tmp/meu-lake`
- Path base: `raw`
- Compressao: `zstd`
- Extracao incremental: `n`
- Expressao cron: (deixe vazio)

Ou crie o arquivo YAML manualmente em `~/.dataspoc-pipe/pipelines/meu-pipeline.yaml`:

```yaml
source:
  tap: tap-csv
  config:
    files:
      - entity: clientes
        path: /tmp/dados/clientes.csv
        keys:
          - id

destination:
  bucket: file:///tmp/meu-lake
  path: raw
  compression: zstd

incremental:
  enabled: false
```

### Passo 5: Valide a configuracao

```bash
dataspoc-pipe validate meu-pipeline
```

Isso testa se o bucket esta acessivel e se o tap esta instalado.

### Passo 6: Execute o pipeline

```bash
dataspoc-pipe run meu-pipeline
```

Saida esperada:

```
Executando: meu-pipeline
  clientes: 5 registros...
Sucesso! 5 registros em 1 stream(s)
  clientes: 5
```

### Passo 7: Verifique os resultados

```bash
# Status geral
dataspoc-pipe status

# Logs da ultima execucao
dataspoc-pipe logs meu-pipeline

# Catalogo do lake
dataspoc-pipe manifest file:///tmp/meu-lake
```

Os dados estao em `/tmp/meu-lake/raw/csv/clientes/dt=YYYY-MM-DD/` como arquivos Parquet.

---

## 4. Configuracao

Cada pipeline e definido por um arquivo YAML em `~/.dataspoc-pipe/pipelines/<nome>.yaml`.

### Estrutura completa do YAML

```yaml
source:
  tap: <string>          # (obrigatorio) Nome do executavel Singer tap
  config: <dict|string>  # (obrigatorio) Configuracao do tap — inline ou path para arquivo
  streams:               # (opcional) Filtro de streams — null = todas
    - stream_a
    - stream_b

destination:
  bucket: <string>       # (obrigatorio) URI do bucket de destino
  path: <string>         # (opcional, default: "raw") Path base no bucket
  partition_by: <string> # (opcional, default: "_extraction_date") Campo de particao
  compression: <string>  # (opcional, default: "zstd") Compressao do Parquet

incremental:
  enabled: <bool>        # (opcional, default: false) Habilitar extracao incremental

schedule:
  cron: <string|null>    # (opcional, default: null) Expressao cron para agendamento
```

### Detalhamento dos campos

#### source

| Campo | Tipo | Obrigatorio | Default | Descricao |
|-------|------|-------------|---------|-----------|
| `tap` | string | Sim | — | Nome do executavel do tap Singer. Deve estar no PATH. Exemplos: `tap-postgres`, `tap-csv`, `tap-github`. |
| `config` | dict ou string | Sim | — | Configuracao passada ao tap via `--config`. Se for um dicionario, sera salvo automaticamente em um arquivo temporario. Se for uma string, e interpretado como caminho para um arquivo JSON. |
| `streams` | lista de strings | Nao | null (todas) | Lista de streams para extrair. Se omitido, todas as streams do tap serao processadas. |

#### destination

| Campo | Tipo | Obrigatorio | Default | Descricao |
|-------|------|-------------|---------|-----------|
| `bucket` | string | Sim | — | URI do bucket. Prefixos aceitos: `s3://`, `gs://`, `az://`, `file://`. |
| `path` | string | Nao | `raw` | Caminho base dentro do bucket onde os dados serao gravados. |
| `partition_by` | string | Nao | `_extraction_date` | Campo usado para particionar os dados no estilo Hive. |
| `compression` | string | Nao | `zstd` | Algoritmo de compressao do Parquet. Opcoes: `zstd`, `snappy`, `gzip`, `none`. |

#### incremental

| Campo | Tipo | Obrigatorio | Default | Descricao |
|-------|------|-------------|---------|-----------|
| `enabled` | bool | Nao | `false` | Quando `true`, o state do tap Singer e salvo apos cada execucao e reutilizado na proxima, permitindo extracao incremental. |

#### schedule

| Campo | Tipo | Obrigatorio | Default | Descricao |
|-------|------|-------------|---------|-----------|
| `cron` | string ou null | Nao | `null` | Expressao cron padrao (5 campos). Se definida, pode ser instalada no crontab do sistema com `dataspoc-pipe schedule install`. |

### Opcoes de compressao

| Algoritmo | Descricao |
|-----------|-----------|
| `zstd` | Melhor relacao compressao/velocidade. Recomendado como padrao. |
| `snappy` | Rapido, boa compatibilidade com ecossistema Hadoop/Spark. |
| `gzip` | Maior compressao, mais lento. Boa compatibilidade universal. |
| `none` | Sem compressao. Util para debug ou volumes pequenos. |

### Configuracao global

O arquivo `~/.dataspoc-pipe/config.yaml` define defaults globais:

```yaml
defaults:
  compression: zstd
  partition_by: _extraction_date
```

---

## 5. Comandos

### init

Inicializa a estrutura de configuracao do DataSpoc Pipe.

```bash
dataspoc-pipe init
```

Cria os diretorios `~/.dataspoc-pipe/` e `~/.dataspoc-pipe/pipelines/`, alem do arquivo de configuracao global `config.yaml`.

Se a estrutura ja existir, nenhuma alteracao e feita.

### add

Cria um novo pipeline atraves de um wizard interativo.

```bash
dataspoc-pipe add <nome>
```

**Exemplo:**

```bash
dataspoc-pipe add vendas-diarias
```

O wizard solicita:
1. Tap Singer (ex: `tap-postgres`)
2. Config do tap (JSON inline ou caminho para arquivo)
3. Bucket de destino (ex: `s3://meu-bucket`)
4. Path base no bucket (default: `raw`)
5. Compressao (default: `zstd`)
6. Se habilita extracao incremental
7. Expressao cron para agendamento (opcional)

O resultado e salvo em `~/.dataspoc-pipe/pipelines/vendas-diarias.yaml`.

### run

Executa um pipeline de extracao.

```bash
# Executar um pipeline especifico
dataspoc-pipe run <nome>

# Forcar extracao completa (ignorar state incremental)
dataspoc-pipe run <nome> --full

# Executar todos os pipelines configurados
dataspoc-pipe run <nome> --all
```

**Exemplos:**

```bash
# Execucao normal
dataspoc-pipe run vendas-diarias

# Reprocessar tudo do zero
dataspoc-pipe run vendas-diarias --full

# Executar todos os pipelines de uma vez
dataspoc-pipe run _ --all
```

O que acontece durante a execucao:

1. Carrega a configuracao do pipeline.
2. Se incremental esta habilitado e `--full` nao foi passado, carrega o state anterior.
3. Executa o tap Singer como subprocesso.
4. Le o stdout linha a linha, parseando mensagens Singer (SCHEMA, RECORD, STATE).
5. Acumula records em um buffer de 10.000 registros por stream.
6. Quando o buffer enche, converte para Parquet e envia ao bucket.
7. Ao final, faz flush dos buffers restantes.
8. Salva o state (se incremental) e atualiza o manifest.
9. Grava log da execucao no bucket.

### status

Exibe uma tabela com o status de todos os pipelines configurados.

```bash
dataspoc-pipe status
```

Saida exemplo:

```
                   Pipelines
┏━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━┳━━━━━━━━━┳━━━━━━━━━━━┓
┃ Pipeline       ┃ Ultima Execucao   ┃ Status  ┃ Duracao ┃ Registros ┃
┡━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━╇━━━━━━━━━╇━━━━━━━━━━━┩
│ vendas-diarias │ 2026-03-20T08:00  │ sucesso │ 12.3s   │ 45000     │
│ clientes       │ 2026-03-19T22:00  │ sucesso │ 3.1s    │ 1200      │
│ logs-app       │ -                 │ sem ex. │ -       │ -         │
└────────────────┴───────────────────┴─────────┴─────────┴───────────┘
```

### logs

Exibe os logs da ultima execucao de um pipeline especifico.

```bash
dataspoc-pipe logs <nome>
```

**Exemplo:**

```bash
dataspoc-pipe logs vendas-diarias
```

A saida e um JSON com detalhes da execucao: horario de inicio e fim, status, total de registros, duracao e eventuais erros.

### validate

Testa as conexoes com fontes e buckets.

```bash
# Validar um pipeline especifico
dataspoc-pipe validate <nome>

# Validar todos os pipelines
dataspoc-pipe validate
```

**Exemplo:**

```bash
dataspoc-pipe validate vendas-diarias
```

Saida esperada:

```
Validando: vendas-diarias
  Bucket OK: s3://meu-bucket
  Tap OK: tap-postgres encontrado no PATH
```

O que e verificado:
- Escrita e leitura no bucket de destino (grava e remove um arquivo de teste).
- Se o executavel do tap esta disponivel no PATH do sistema.

### manifest

Exibe o catalogo (manifest) de um bucket.

```bash
dataspoc-pipe manifest <bucket-uri>
```

**Exemplo:**

```bash
dataspoc-pipe manifest s3://meu-bucket
dataspoc-pipe manifest file:///tmp/meu-lake
```

O manifest lista todas as tabelas extraidas, suas particoes e metadados. Se nenhuma extracao foi feita no bucket, a mensagem "Manifest vazio" e exibida.

### schedule install

Instala os agendamentos (cron) de todos os pipelines que possuem `schedule.cron` definido.

```bash
dataspoc-pipe schedule install
```

Para cada pipeline com cron configurado, cria uma entrada no crontab do usuario. Usa `flock` para evitar execucoes sobrepostas. O comando e idempotente: se uma entrada para o mesmo pipeline ja existir, ela e substituida com a configuracao atual. Basta rodar `install` novamente apos alterar uma expressao cron para atualizar o crontab.

`python-crontab` e uma dependencia principal -- nao requer instalacao extra.

### schedule remove

Remove todos os agendamentos do DataSpoc Pipe do crontab.

```bash
dataspoc-pipe schedule remove
```

Remove somente as entradas do crontab que tenham o comentario `dataspoc-pipe:*`. Outras entradas do crontab permanecem intactas.

---

## 6. Extracao incremental

### Como funciona

A extracao incremental permite que o tap Singer extraia apenas os dados novos ou alterados desde a ultima execucao, em vez de reprocessar toda a fonte a cada vez.

O mecanismo funciona assim:

1. Na primeira execucao, o tap extrai todos os dados (full).
2. Durante a extracao, o tap emite mensagens `STATE` no stdout com bookmarks (marcadores de posicao).
3. O DataSpoc Pipe salva o ultimo state no bucket em `.dataspoc/state/<pipeline>/state.json`.
4. Na proxima execucao, o DataSpoc Pipe carrega o state salvo e passa ao tap via `--state`.
5. O tap usa esse state para iniciar a extracao a partir do ponto onde parou.

### Configuracao

Habilite no YAML do pipeline:

```yaml
incremental:
  enabled: true
```

### Onde o state e armazenado

O arquivo de state fica no proprio bucket de destino:

```
bucket/
  .dataspoc/
    state/
      <nome-do-pipeline>/
        state.json
```

### Forcando extracao completa

Mesmo com incremental habilitado, voce pode forcar uma extracao completa a qualquer momento:

```bash
dataspoc-pipe run meu-pipeline --full
```

Isso ignora o state salvo e executa o tap sem `--state`. O novo state gerado pela execucao completa substitui o anterior.

### Quando usar incremental

| Cenario | Recomendacao |
|---------|-------------|
| Tabela com milhoes de registros que cresce diariamente | Habilitar incremental |
| Arquivo CSV estatico | Manter desabilitado |
| API com paginacao por data | Habilitar incremental |
| Primeira carga de um pipeline novo | Executar sem `--full` (a primeira execucao e sempre full) |
| Suspeita de dados corrompidos | Executar com `--full` para reprocessar |

---

## 7. Multi-cloud

O DataSpoc Pipe funciona com qualquer provedor de armazenamento. O prefixo da URI do bucket determina qual backend e usado.

### Provedores suportados

| Provedor | Prefixo URI | Pacote extra |
|----------|-------------|--------------|
| AWS S3 | `s3://` | `dataspoc-pipe[s3]` |
| Google Cloud Storage | `gs://` | `dataspoc-pipe[gcs]` |
| Azure Blob Storage | `az://` | `dataspoc-pipe[azure]` |
| Sistema de arquivos local | `file://` | (nenhum — ja incluso) |

### AWS S3

**Instalacao:**

```bash
pip install dataspoc-pipe[s3]
```

**Configuracao de credenciais:**

O DataSpoc Pipe usa as mesmas credenciais que o AWS CLI. Configure de uma das formas:

1. Variaveis de ambiente:

```bash
export AWS_ACCESS_KEY_ID=sua-access-key
export AWS_SECRET_ACCESS_KEY=sua-secret-key
export AWS_DEFAULT_REGION=us-east-1
```

2. Arquivo de credenciais (`~/.aws/credentials`):

```ini
[default]
aws_access_key_id = sua-access-key
aws_secret_access_key = sua-secret-key
```

3. IAM Role (quando executando em EC2 ou ECS, as credenciais sao atribuidas automaticamente).

**Exemplo de pipeline:**

```yaml
destination:
  bucket: s3://minha-empresa-datalake
  path: raw
  compression: zstd
```

### Google Cloud Storage

**Instalacao:**

```bash
pip install dataspoc-pipe[gcs]
```

**Configuracao de credenciais:**

1. Variavel de ambiente apontando para o arquivo de service account:

```bash
export GOOGLE_APPLICATION_CREDENTIALS=/caminho/para/service-account.json
```

2. Login via gcloud CLI:

```bash
gcloud auth application-default login
```

**Exemplo de pipeline:**

```yaml
destination:
  bucket: gs://minha-empresa-datalake
  path: raw
  compression: zstd
```

### Azure Blob Storage

**Instalacao:**

```bash
pip install dataspoc-pipe[azure]
```

**Configuracao de credenciais:**

1. Variavel de ambiente com a connection string:

```bash
export AZURE_STORAGE_CONNECTION_STRING="DefaultEndpointsProtocol=https;AccountName=...;AccountKey=...;EndpointSuffix=core.windows.net"
```

2. Login via Azure CLI:

```bash
az login
```

**Exemplo de pipeline:**

```yaml
destination:
  bucket: az://meu-container
  path: raw
  compression: zstd
```

### Sistema de arquivos local

Nao requer pacotes extras nem configuracao de credenciais.

**Exemplo de pipeline:**

```yaml
destination:
  bucket: file:///dados/lake
  path: raw
  compression: zstd
```

O diretorio sera criado automaticamente se nao existir.

---

## 8. Convencao de diretorios

O DataSpoc Pipe segue uma convencao padronizada para organizar os dados no bucket. Essa convencao e um **contrato publico estavel** — outros produtos da plataforma DataSpoc (como o Lens) dependem dela para auto-discovery.

### Estrutura completa

```
bucket/
  .dataspoc/
    manifest.json                              # Catalogo do lake
    state/<pipeline>/state.json                # Bookmarks para incremental
    logs/<pipeline>/<timestamp>.json           # Logs de execucao
  raw/
    <fonte>/<tabela>/
      dt=YYYY-MM-DD/
        <tabela>_0000.parquet                  # Dados particionados (Hive-style)
        <tabela>_0001.parquet
```

### Detalhamento

#### .dataspoc/manifest.json

Catalogo central do lake. Lista todas as tabelas, suas fontes e metadados. Atualizado automaticamente a cada execucao bem-sucedida.

#### .dataspoc/state/\<pipeline\>/state.json

Arquivo de state do Singer para extracao incremental. Contem os bookmarks (marcadores) que indicam ate onde a extracao anterior chegou.

#### .dataspoc/logs/\<pipeline\>/\<timestamp\>.json

Log de cada execucao do pipeline. Contem: horario de inicio e fim, status (sucesso/falha), total de registros, duracao e eventuais erros.

#### raw/\<fonte\>/\<tabela\>/dt=YYYY-MM-DD/

Os dados propriamente ditos. Organizados por:

- **fonte**: derivado do nome do tap (ex: `tap-postgres` vira `postgres`).
- **tabela**: nome da stream Singer.
- **dt=YYYY-MM-DD**: particao no estilo Hive pela data de extracao.

#### Nomes dos arquivos Parquet

Os arquivos seguem o padrao `<tabela>_NNNN.parquet`, onde `NNNN` e um numero sequencial (0000, 0001, ...). Cada arquivo contem ate 10.000 registros (tamanho do batch interno).

---

## 9. Transforms

### O que sao transforms?

Transforms permitem limpar, filtrar ou reformatar dados durante a ingestao -- antes de serem escritos como Parquet. Sao baseados em convencao: se um arquivo Python existir em `~/.dataspoc-pipe/transforms/<nome_do_pipeline>.py`, ele e executado automaticamente ao rodar `dataspoc-pipe run <nome_do_pipeline>`. Nenhuma configuracao adicional e necessaria.

### Como funciona

O transform e aplicado por batch (~10.000 registros) durante a ingestao, entre a saida do Singer tap e a escrita do Parquet:

```
fonte → tap → batch → transform(df) [se existir] → Parquet → bucket
```

- Se nao existir arquivo de transform para o pipeline, ele roda normalmente (dados brutos sao escritos como estao).
- Se o arquivo de transform existir mas falhar em tempo de execucao, o pipeline continua com os dados brutos e um aviso e exibido.

### Criando um transform

Crie um arquivo Python em `~/.dataspoc-pipe/transforms/` com o mesmo nome do pipeline. O arquivo deve definir uma funcao `transform(df)` que recebe um pandas DataFrame e retorna um pandas DataFrame.

**Exemplo**: limpar pedidos durante a ingestao (`~/.dataspoc-pipe/transforms/orders.py`):

```python
# ~/.dataspoc-pipe/transforms/orders.py
import pandas as pd

def transform(df):
    """Limpa pedidos durante a ingestao."""
    df = df.drop_duplicates(subset=["order_id"])
    df["email"] = df["email"].str.lower().str.strip()
    df = df[df["order_status"] != "cancelled"]
    df["order_date"] = pd.to_datetime(df["order_date"])
    return df
```

### Estrutura de diretorios

```
~/.dataspoc-pipe/
  config.yaml
  pipelines/
    orders.yaml          ← definicao do pipeline
  sources/
    orders.json          ← config da fonte
  transforms/            ← NOVO
    orders.py            ← mesmo nome do pipeline, executa automaticamente
```

### Regras

1. **Baseado em convencao** -- o nome do arquivo de transform deve ser igual ao nome do pipeline (sem `.yaml`).
2. **Sem configuracao** -- basta criar o arquivo `.py` e ele roda no proximo `dataspoc-pipe run`.
3. **Assinatura da funcao** -- o arquivo deve definir `def transform(df)` que recebe e retorna um pandas DataFrame.
4. **Execucao por batch** -- a funcao e chamada uma vez por batch (~10K registros), nao uma vez para toda a extracao.
5. **Tolerante a falhas** -- se o transform lancar uma excecao, o batch e escrito com dados brutos e um aviso e exibido. O pipeline nao aborta.

### Quando usar transforms

| Caso de uso | Exemplo |
|-------------|---------|
| Remover duplicatas | `df.drop_duplicates(subset=["id"])` |
| Normalizar campos de texto | `df["email"] = df["email"].str.lower().str.strip()` |
| Filtrar linhas indesejadas | `df = df[df["status"] != "deleted"]` |
| Parsear datas | `df["date"] = pd.to_datetime(df["date"])` |
| Renomear colunas | `df = df.rename(columns={"old": "new"})` |
| Adicionar colunas calculadas | `df["total"] = df["qty"] * df["price"]` |

### Quando NAO usar transforms

Transforms sao para limpeza leve durante a ingestao. Para transformacoes complexas (joins, agregacoes, logica multi-tabela), use os transforms do DataSpoc Lens.

---

## 10. Agendamento

O DataSpoc Pipe pode agendar a execucao dos pipelines usando o crontab do sistema operacional. O pacote `python-crontab` e uma dependencia principal -- ja vem instalado com o `pip install dataspoc-pipe`, sem necessidade de instalacao extra.

### Passo 1: Adicione `schedule.cron` ao YAML do pipeline

Adicione o campo `schedule.cron` na definicao do pipeline:

```yaml
source:
  tap: tap-postgres
  config:
    host: db.minha-empresa.com.br
    port: 5432
    user: etl_reader
    password: senha-segura
    dbname: producao

destination:
  bucket: s3://minha-empresa-datalake
  path: raw
  compression: zstd

incremental:
  enabled: true

schedule:
  cron: "0 */6 * * *"   # A cada 6 horas
```

O valor de `schedule.cron` e uma expressao cron padrao de cinco campos.

### Passo 2: Instale os agendamentos

```bash
dataspoc-pipe schedule install
```

Isso cria uma entrada no crontab do usuario atual para cada pipeline que tenha `schedule.cron` definido. Comportamentos importantes:

- **Protecao contra sobreposicao**: cada entrada no cron usa `flock` para evitar execucoes concorrentes do mesmo pipeline. Se uma execucao anterior ainda estiver em andamento, a nova invocacao e ignorada.
- **Idempotente**: executar `schedule install` novamente atualiza as entradas existentes. Se voce alterar a expressao cron no YAML, basta rodar `install` novamente para aplicar -- a entrada antiga e substituida, sem duplicacao.

### Passo 3 (opcional): Remova os agendamentos

```bash
dataspoc-pipe schedule remove
```

Remove todas as entradas do DataSpoc Pipe do crontab. Somente entradas identificadas pelo prefixo de comentario `dataspoc-pipe:` sao removidas; outras entradas do crontab permanecem intactas.

### Verificando agendamentos instalados

```bash
crontab -l | grep dataspoc-pipe
```

### Expressoes cron comuns

| Expressao | Significado |
|-----------|-------------|
| `0 * * * *` | A cada hora, no minuto 0 |
| `0 */6 * * *` | A cada 6 horas |
| `0 2 * * *` | Diariamente as 2h da manha (ideal para ETL noturno) |
| `0 0 * * 1` | Toda segunda-feira a meia-noite |
| `0 0 1 * *` | No primeiro dia de cada mes |
| `*/30 * * * *` | A cada 30 minutos |
| `0 6,18 * * *` | Duas vezes ao dia: 6h e 18h |
| `0 8 * * 1-5` | De segunda a sexta as 8h |

### Formato da expressao cron

```
┌─────────── minuto (0-59)
│ ┌───────── hora (0-23)
│ │ ┌─────── dia do mes (1-31)
│ │ │ ┌───── mes (1-12)
│ │ │ │ ┌─── dia da semana (0-7, 0 e 7 = domingo)
│ │ │ │ │
* * * * *
```

### Dependencia: python-crontab

`python-crontab` e uma **dependencia principal** do DataSpoc Pipe e e instalado automaticamente com `pip install dataspoc-pipe`. Nenhuma instalacao extra e necessaria.

---

## 11. Troubleshooting

### Tap nao encontrado

**Erro:**

```
Tap 'tap-postgres' nao encontrado. Instale com: pip install tap-postgres
```

**Causa:** O executavel do tap Singer nao esta no PATH.

**Solucoes:**

1. Instale o tap:

```bash
pip install tap-postgres
```

2. Se voce esta usando um virtualenv, certifique-se de que o ambiente esta ativado:

```bash
source /caminho/para/venv/bin/activate
```

3. Verifique se o tap esta acessivel:

```bash
which tap-postgres
```

### Bucket inacessivel (S3)

**Erro:** Falha ao escrever no bucket S3.

**Solucoes:**

1. Verifique se as credenciais estao configuradas:

```bash
aws sts get-caller-identity
```

2. Verifique se o bucket existe e voce tem permissao:

```bash
aws s3 ls s3://meu-bucket/
```

3. Verifique se o pacote extra esta instalado:

```bash
pip install dataspoc-pipe[s3]
```

### Bucket inacessivel (GCS)

**Erro:** Falha ao escrever no bucket GCS.

**Solucoes:**

1. Verifique se o arquivo de credenciais esta configurado:

```bash
echo $GOOGLE_APPLICATION_CREDENTIALS
```

2. Teste o acesso:

```bash
gsutil ls gs://meu-bucket/
```

3. Verifique se o pacote extra esta instalado:

```bash
pip install dataspoc-pipe[gcs]
```

### Bucket inacessivel (Azure)

**Erro:** Falha ao escrever no Azure Blob Storage.

**Solucoes:**

1. Verifique a connection string:

```bash
echo $AZURE_STORAGE_CONNECTION_STRING
```

2. Verifique se o pacote extra esta instalado:

```bash
pip install dataspoc-pipe[azure]
```

### Pipeline nao encontrado

**Erro:**

```
Pipeline 'vendas' nao encontrado em /home/usuario/.dataspoc-pipe/pipelines/vendas.yaml
```

**Solucoes:**

1. Verifique o nome do pipeline:

```bash
ls ~/.dataspoc-pipe/pipelines/
```

2. Crie o pipeline se necessario:

```bash
dataspoc-pipe add vendas
```

### Erro de permissao no bucket local

**Erro:** Permission denied ao escrever em `file:///caminho/para/lake`.

**Solucao:** Certifique-se de que o usuario tem permissao de escrita no diretorio:

```bash
chmod -R u+w /caminho/para/lake
```

### Tap falhou com exit code diferente de zero

**Erro:**

```
Tap falhou (exit code 1): <mensagem de erro>
```

**Causa:** O tap Singer retornou um erro. Pode ser problema de conexao com a fonte, configuracao invalida ou bug no tap.

**Solucoes:**

1. Execute o tap manualmente para ver o erro completo:

```bash
tap-postgres --config config.json
```

2. Verifique se a configuracao do tap no YAML esta correta (host, porta, usuario, senha, banco).

3. Teste a conectividade com a fonte de dados diretamente.

### python-crontab nao encontrado

**Erro:**

```
No module named 'crontab'
```

**Causa:** A instalacao do DataSpoc Pipe pode estar incompleta ou corrompida.

**Solucao:** Reinstale o DataSpoc Pipe, que inclui `python-crontab` como dependencia principal:

```bash
pip install --force-reinstall dataspoc-pipe
```

### Dados nao aparecem no manifest

**Causa:** O manifest so e atualizado apos uma execucao bem-sucedida.

**Solucoes:**

1. Verifique se a execucao foi bem-sucedida:

```bash
dataspoc-pipe status
dataspoc-pipe logs meu-pipeline
```

2. Execute o pipeline novamente e observe se ha erros.

---

## 12. Exemplos praticos

### Exemplo 1: tap-csv para bucket local

Cenario: Voce tem arquivos CSV locais e quer converter para Parquet em um diretorio local.

**Instalacao:**

```bash
pip install dataspoc-pipe tap-csv
```

**Arquivo de dados** (`/dados/vendas.csv`):

```csv
id,produto,quantidade,valor,data_venda
1,Widget A,10,99.90,2026-01-15
2,Widget B,5,149.90,2026-01-16
3,Widget A,20,99.90,2026-01-17
4,Widget C,3,299.90,2026-01-18
5,Widget B,15,149.90,2026-01-19
```

**Pipeline** (`~/.dataspoc-pipe/pipelines/vendas-csv.yaml`):

```yaml
source:
  tap: tap-csv
  config:
    files:
      - entity: vendas
        path: /dados/vendas.csv
        keys:
          - id

destination:
  bucket: file:///dados/lake
  path: raw
  compression: zstd

incremental:
  enabled: false
```

**Execucao:**

```bash
dataspoc-pipe run vendas-csv
```

**Resultado no disco:**

```
/dados/lake/
  .dataspoc/
    manifest.json
    logs/vendas-csv/2026-03-20T080000Z.json
  raw/
    csv/vendas/
      dt=2026-03-20/
        vendas_0000.parquet
```

---

### Exemplo 2: tap-postgres para S3

Cenario: Voce tem um banco PostgreSQL e quer extrair dados incrementalmente para um bucket S3.

**Instalacao:**

```bash
pip install dataspoc-pipe[s3] tap-postgres
```

**Configuracao de credenciais AWS:**

```bash
export AWS_ACCESS_KEY_ID=AKIA...
export AWS_SECRET_ACCESS_KEY=secret...
export AWS_DEFAULT_REGION=sa-east-1
```

**Pipeline** (`~/.dataspoc-pipe/pipelines/postgres-vendas.yaml`):

```yaml
source:
  tap: tap-postgres
  config:
    host: db.minha-empresa.com.br
    port: 5432
    user: etl_reader
    password: senha-segura
    dbname: producao
    filter_schemas: public
    filter_tables: vendas,clientes,produtos

destination:
  bucket: s3://minha-empresa-datalake
  path: raw
  compression: zstd

incremental:
  enabled: true

schedule:
  cron: "0 2 * * *"
```

**Execucao inicial (full):**

```bash
dataspoc-pipe run postgres-vendas
```

**Execucoes seguintes (incremental, automaticamente):**

```bash
# Manual
dataspoc-pipe run postgres-vendas

# Ou instale o agendamento para executar automaticamente as 2h
dataspoc-pipe schedule install
```

**Resultado no S3:**

```
s3://minha-empresa-datalake/
  .dataspoc/
    manifest.json
    state/postgres-vendas/state.json
    logs/postgres-vendas/2026-03-20T020000Z.json
  raw/
    postgres/vendas/
      dt=2026-03-20/
        vendas_0000.parquet
    postgres/clientes/
      dt=2026-03-20/
        clientes_0000.parquet
    postgres/produtos/
      dt=2026-03-20/
        produtos_0000.parquet
```

**Reprocessamento completo (quando necessario):**

```bash
dataspoc-pipe run postgres-vendas --full
```

---

### Exemplo 3: tap-github para GCS

Cenario: Voce quer extrair dados de repositorios do GitHub (issues, pull requests, commits) e armazenar no Google Cloud Storage.

**Instalacao:**

```bash
pip install dataspoc-pipe[gcs] tap-github
```

**Configuracao de credenciais GCS:**

```bash
export GOOGLE_APPLICATION_CREDENTIALS=/home/usuario/sa-datalake.json
```

**Pipeline** (`~/.dataspoc-pipe/pipelines/github-meuprojeto.yaml`):

```yaml
source:
  tap: tap-github
  config:
    access_token: ghp_seu-token-aqui
    repository: minha-org/meu-repo
  streams:
    - issues
    - pull_requests
    - commits

destination:
  bucket: gs://minha-empresa-datalake
  path: raw
  compression: snappy

incremental:
  enabled: true

schedule:
  cron: "0 8 * * 1-5"
```

**Execucao:**

```bash
# Validar antes de rodar
dataspoc-pipe validate github-meuprojeto

# Executar
dataspoc-pipe run github-meuprojeto

# Verificar
dataspoc-pipe status
dataspoc-pipe manifest gs://minha-empresa-datalake
```

**Resultado no GCS:**

```
gs://minha-empresa-datalake/
  .dataspoc/
    manifest.json
    state/github-meuprojeto/state.json
    logs/github-meuprojeto/2026-03-20T080000Z.json
  raw/
    github/issues/
      dt=2026-03-20/
        issues_0000.parquet
    github/pull_requests/
      dt=2026-03-20/
        pull_requests_0000.parquet
    github/commits/
      dt=2026-03-20/
        commits_0000.parquet
        commits_0001.parquet
```

Neste exemplo, o campo `streams` filtra apenas as streams desejadas do tap-github, e o agendamento executa de segunda a sexta as 8h. Como `incremental` esta habilitado, apenas commits, issues e PRs novos sao extraidos a cada execucao.
