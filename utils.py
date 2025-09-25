# utils.py
import pandas as pd
import numpy as np

def infer_types(df: pd.DataFrame) -> dict:
    """
    Separa colunas em categorias simples: numéricas e texto/categóricas.
    Retorna: {"numeric": [...], "text": [...]} (ordem estável)
    """
    numeric = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
    text = [c for c in df.columns if c not in numeric]
    return {"numeric": numeric, "text": text}

def basic_stats(df: pd.DataFrame) -> dict:
    """
    Calcula estatísticas gerais do dataset e um resumo por coluna.
    Retorna um dicionário com:
      - shape, memory_mb, nulls_total, duplicates
      - describe_num (describe numérico)
      - top_categories (top 10 categorias por coluna categórica)
    """
    info = {
        "shape": df.shape,
        "memory_mb": df.memory_usage(deep=True).sum() / 1024**2,
        "nulls_total": int(df.isnull().sum().sum()),
        "duplicates": int(df.duplicated().sum()),
    }
    num_cols = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
    info["describe_num"] = df[num_cols].describe().round(3) if num_cols else None

    cat_cols = [c for c in df.columns if c not in num_cols]
    top = {}
    for c in cat_cols[:10]:  # limita p/ não exagerar
        vc = df[c].astype(str).value_counts(dropna=False).head(10)
        top[c] = vc
    info["top_categories"] = top
    return info

def aggregate(df: pd.DataFrame, x: str, y: str | None, how: str) -> pd.DataFrame:
    """
    Agrega df por coluna x. Se y for None, usa contagem.
    how: 'soma','média','contagem','mediana','máximo','mínimo'
    """
    how_map = {
        "soma": "sum",
        "média": "mean",
        "contagem": "count",
        "mediana": "median",
        "máximo": "max",
        "mínimo": "min",
    }
    if y is None or how == "contagem":
        out = df.groupby(x, dropna=False).size().reset_index(name="valor")
        out.rename(columns={x: "x"}, inplace=True)
        return out
    func = how_map.get(how, "sum")
    out = df.groupby(x, dropna=False)[y].agg(func).reset_index()
    out.rename(columns={x: "x", y: "valor"}, inplace=True)
    return out

import pandas as pd

# --- DETECÇÃO E CONVERSÃO DE DATAS ---
def detect_datetime_cols(df: pd.DataFrame) -> list[str]:
    """
    Tenta detectar colunas de data/hora por dtype e por nome.
    Retorna lista (pode ser vazia).
    """
    candidates = []
    # por dtype já datetime
    for c in df.columns:
        if pd.api.types.is_datetime64_any_dtype(df[c]):
            candidates.append(c)

    # por nome + tentativa de parse (leve)
    name_hints = ("data", "date", "created", "updated", "timestamp", "time", "dt_", "_dt")
    for c in df.columns:
        lc = str(c).lower()
        if any(h in lc for h in name_hints) and c not in candidates:
            try:
                pd.to_datetime(df[c], errors="raise", infer_datetime_format=True)
                candidates.append(c)
            except Exception:
                pass
    # ordem estável/sem duplicatas
    seen, out = set(), []
    for c in candidates:
        if c not in seen:
            seen.add(c); out.append(c)
    return out

def ensure_datetime(series: pd.Series) -> pd.Series:
    """Converte série para datetime (na marra, quando possível)."""
    if pd.api.types.is_datetime64_any_dtype(series):
        return series
    return pd.to_datetime(series, errors="coerce", infer_datetime_format=True)

# --- AGREGAÇÃO TEMPORAL ---
def time_aggregate(df: pd.DataFrame, date_col: str, y: str | None, how: str, freq: str) -> pd.DataFrame:
    """
    Agrupa por período temporal.
      freq: 'D' (dia), 'W' (semana), 'M' (mês), 'Q' (trimestre), 'Y' (ano)
      how:  'soma','média','contagem','mediana','máximo','mínimo'
    Retorna DataFrame com colunas: ['x', 'valor'] (x = data do período)
    """
    how_map = {
        "soma": "sum",
        "média": "mean",
        "contagem": "count",
        "mediana": "median",
        "máximo": "max",
        "mínimo": "min",
    }
    sdt = ensure_datetime(df[date_col])
    tmp = df.copy()
    tmp["_dt"] = sdt

    if y is None or how == "contagem":
        grouped = tmp.set_index("_dt").resample(freq).size().reset_index(name="valor")
    else:
        func = how_map.get(how, "sum")
        grouped = tmp.set_index("_dt")[y].resample(freq).agg(func).reset_index(name="valor")

    grouped.rename(columns={"_dt": "x"}, inplace=True)
    # garante ordenação por data
    grouped = grouped.sort_values("x").reset_index(drop=True)
    return grouped
