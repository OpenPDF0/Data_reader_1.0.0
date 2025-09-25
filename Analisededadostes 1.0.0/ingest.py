"""
ingest.py — Biblioteca de leitura genérica de arquivos tabulares.

Objetivo:
---------
Fornecer uma função única (`read_any`) para ler arquivos CSV, Excel (.xlsx/.xls)
e JSON/NDJSON e devolver um pandas.DataFrame limpinho para o app.

O que faz:
----------
- Detecta o tipo de arquivo pela extensão.
- CSV: tenta combinações comuns de encoding e separador.
- Excel: carrega a primeira planilha por padrão (UI pode expor seleção).
- JSON: aceita JSON "array" ou NDJSON (um JSON por linha).
- Limpeza leve: remove colunas 'Unnamed', strip nos nomes e reseta índice.

Dependências:
-------------
- pandas
- (opcional) openpyxl para .xlsx
- (opcional) xlrd para .xls

Uso típico:
-----------
from ingest import read_any
df = read_any(uploaded_file)  # uploaded_file = st.file_uploader(...) no Streamlit
"""

from __future__ import annotations

import io
import json
from typing import Any

import pandas as pd


def read_any(uploaded_file: Any) -> pd.DataFrame:
    """
    Roteia a leitura conforme a extensão do arquivo e retorna um DataFrame.

    Suporta:
      - .csv
      - .xlsx / .xls
      - .json (array) / NDJSON (linha a linha)

    Args:
        uploaded_file: objeto retornado por st.file_uploader (possui .name e .read()).

    Returns:
        pd.DataFrame: Dados carregados e limpos.

    Raises:
        ValueError: Se a extensão não for suportada.
    """
    name = uploaded_file.name.lower()
    if name.endswith(".csv"):
        return _read_csv(uploaded_file)
    if name.endswith((".xlsx", ".xls")):
        return _read_excel(uploaded_file)
    if name.endswith(".json"):
        return _read_json(uploaded_file)
    raise ValueError("Formato não suportado. Use CSV, XLSX/XLS ou JSON.")


def _read_csv(f: Any) -> pd.DataFrame:
    """
    Leitor CSV robusto (uso interno).

    Estratégia:
      1) Lê os bytes do arquivo.
      2) Tenta pares de (encoding, separador) mais comuns.
         Encodings testados: ['utf-8', 'latin-1']
         Separadores testados: [',', ';', '\\t', '|']

    Obs:
      - Caso seu CSV seja muito exótico, adicione mais encodings/separadores aqui.
      - Pode-se evoluir futuramente para `engine="python", sep=None` (inferência),
        mas aqui mantemos explícito para previsibilidade.

    Args:
        f: arquivo-like com .read() e .seek()

    Returns:
        pd.DataFrame: dados lidos e limpos via _clean().

    Raises:
        ValueError: se nenhuma combinação funcionar.
    """
    raw = f.read()
    f.seek(0)

    for enc in ["utf-8", "latin-1"]:
        for sep in [",", ";", "\t", "|"]:
            try:
                df = pd.read_csv(io.BytesIO(raw), encoding=enc, sep=sep)
                f.seek(0)
                return _clean(df)
            except Exception:
                f.seek(0)
                continue

    raise ValueError("CSV com encoding/separador não detectado.")


def _read_excel(f: Any) -> pd.DataFrame:
    """
    Leitor Excel (uso interno).

    Estratégia:
      - Lê os bytes e usa `pd.ExcelFile` para identificar planilhas.
      - Por padrão, carrega a **primeira planilha** (pensado para backend).
      - A UI do app pode oferecer seleção de planilha quando necessário.

    Args:
        f: arquivo-like com .read() e .seek()

    Returns:
        pd.DataFrame: dados lidos da primeira planilha, pós _clean().
    """
    raw = f.read()
    f.seek(0)

    xls = pd.ExcelFile(io.BytesIO(raw))
    first_sheet = xls.sheet_names[0]
    df = pd.read_excel(io.BytesIO(raw), sheet_name=first_sheet)
    return _clean(df)


def _read_json(f: Any) -> pd.DataFrame:
    """
    Leitor JSON (uso interno).

    Suporta:
      - JSON array (lista de objetos): [{"a":1, "b":2}, {...}]
      - NDJSON (um JSON por linha)

    Estratégia:
      1) Decodifica como UTF-8 (ignorando erros).
      2) Tenta `json.loads` direto.
      3) Se falhar, faz split por linhas e carrega cada JSON.

    Args:
        f: arquivo-like com .read() e .seek()

    Returns:
        pd.DataFrame: dados normalizados via pandas.json_normalize, pós _clean().
    """
    raw = f.read().decode("utf-8", errors="ignore").strip()
    f.seek(0)

    try:
        data = json.loads(raw)
        if isinstance(data, dict):
            data = [data]  # normaliza dict único para lista de dicts
    except Exception:
        # NDJSON: cada linha é um JSON válido
        data = [json.loads(line) for line in raw.splitlines() if line.strip()]

    return _clean(pd.json_normalize(data))


def _clean(df: pd.DataFrame) -> pd.DataFrame:
    """
    Limpeza leve aplicada a todos os formatos.

    - Remove colunas artificiais 'Unnamed...' (geradas em exportações do Excel/CSV).
    - Faz strip nos nomes das colunas (remove espaços nas extremidades).
    - Dá reset no índice.

    Args:
        df: DataFrame bruto após leitura.

    Returns:
        pd.DataFrame: DataFrame pronto para exibição/uso.
    """
    df.columns = [str(c).strip() for c in df.columns]
    df = df.loc[:, ~pd.Series(df.columns).astype(str).str.match(r"^Unnamed")]
    return df.reset_index(drop=True)
