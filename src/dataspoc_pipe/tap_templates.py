"""Templates de configuração para taps Singer conhecidos."""

BUILTIN_TAPS = {
    "google-sheets-public": "dataspoc_pipe.builtin_taps.google_sheets_public",
    "parquet": "dataspoc_pipe.builtin_taps.parquet",
}

TEMPLATES = {
    "parquet": {
        "_comment": "Read Parquet files from a bucket or local path. Used for raw → curated pipelines.",
        "path": "s3://bucket/raw/source/table",
        "stream_name": "table_name",
    },
    "google-sheets-public": {
        "_comment": "Public Google Sheets (no OAuth). Paste the full URL from your browser. The spreadsheet ID and sheet (gid) are extracted automatically.",
        "url": "PASTE_SPREADSHEET_URL_HERE",
        "sheet_name": "sheet",
    },
    "tap-google-sheets": {
        "_comment": "Requer OAuth: client_id, client_secret, refresh_token (via Google Cloud Console)",
        "spreadsheet_id": "COLE_O_ID_DA_PLANILHA_AQUI",
        "client_id": "SEU_CLIENT_ID",
        "client_secret": "SEU_CLIENT_SECRET",
        "refresh_token": "SEU_REFRESH_TOKEN",
        "user_agent": "dataspoc-pipe",
        "start_date": "2000-01-01T00:00:00Z",
    },
    "tap-postgres": {
        "host": "localhost",
        "port": 5432,
        "user": "SEU_USUARIO",
        "password": "SUA_SENHA",
        "dbname": "SEU_BANCO",
        "filter_schemas": "public",
        "default_replication_method": "FULL_TABLE",
    },
    "tap-mysql": {
        "host": "localhost",
        "port": 3306,
        "user": "SEU_USUARIO",
        "password": "SUA_SENHA",
        "database": "SEU_BANCO",
    },
    "tap-csv": {
        "files": [
            {
                "entity": "NOME_DA_TABELA",
                "path": "/caminho/para/arquivo.csv",
                "keys": ["id"],
            }
        ],
    },
    "tap-s3-csv": {
        "aws_access_key_id": "",
        "aws_secret_access_key": "",
        "bucket": "SEU_BUCKET",
        "tables": [
            {
                "table_name": "NOME_DA_TABELA",
                "search_prefix": "caminho/no/bucket",
                "search_pattern": ".*\\.csv",
            }
        ],
    },
    "tap-github": {
        "access_token": "SEU_TOKEN_GITHUB",
        "repository": "owner/repo",
        "start_date": "2024-01-01T00:00:00Z",
    },
    "tap-rest-api": {
        "api_url": "https://api.exemplo.com",
        "headers": {"Authorization": "Bearer SEU_TOKEN"},
        "streams": [
            {
                "name": "NOME_DO_ENDPOINT",
                "path": "/v1/endpoint",
            }
        ],
    },
    "tap-mongodb": {
        "host": "localhost",
        "port": 27017,
        "user": "SEU_USUARIO",
        "password": "SUA_SENHA",
        "database": "SEU_BANCO",
    },
    "tap-salesforce": {
        "client_id": "SEU_CLIENT_ID",
        "client_secret": "SEU_CLIENT_SECRET",
        "refresh_token": "SEU_REFRESH_TOKEN",
        "start_date": "2024-01-01T00:00:00Z",
        "api_type": "BULK",
    },
}


def get_template(tap_name: str) -> dict | None:
    """Retorna template de config para um tap, ou None se desconhecido."""
    return TEMPLATES.get(tap_name)


def list_known_taps() -> list[str]:
    """Lista taps com template disponível."""
    return sorted(TEMPLATES.keys())


def try_discover_config(tap_name: str) -> dict | None:
    """Tenta rodar tap --about ou tap --discover para descobrir config."""
    import subprocess
    import json

    for flag in ["--about", "--discover"]:
        try:
            result = subprocess.run(
                [tap_name, flag],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode == 0 and result.stdout.strip():
                data = json.loads(result.stdout)
                # Extrair settings se disponível
                if "settings" in data:
                    return {s["name"]: "" for s in data["settings"] if s.get("required", False)}
                return {}
        except Exception:
            continue
    return None
