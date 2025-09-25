import pandas as pd
import plotly.express as px

def plot_generic(tipo: str, df: pd.DataFrame, x: str, y: str | None = None, color: str | None = None, aggregated: bool = False):
    """
    tipos: Barras, Linha, Pizza, Histograma, Scatter
    aggregated=True => df deve ter colunas 'x' e 'valor'
    """
    # se veio agregado e x é data, garante ordenação
    if aggregated and "x" in df.columns:
        if pd.api.types.is_datetime64_any_dtype(df["x"]):
            df = df.sort_values("x").reset_index(drop=True)

    if tipo == "Barras":
        if aggregated:
            return px.bar(df, x="x", y="valor", color=color, title="Barras — Agregado")
        if y is None:
            return px.bar(df, x=x, color=color, title=f"Barras — Contagem por {x}")
        grouped = df.groupby(x, dropna=False)[y].sum().reset_index()
        return px.bar(grouped, x=x, y=y, color=color, title=f"Barras — {y} por {x}")

    elif tipo == "Linha":
        if aggregated:
            return px.line(df, x="x", y="valor", color=color, markers=True, title="Linha — Agregado")
        if y is None:
            raise ValueError("Para Linha, selecione Y numérico.")
        grouped = df.groupby(x, dropna=False)[y].sum().reset_index()
        return px.line(grouped, x=x, y=y, color=color, markers=True, title=f"Linha — {y} por {x}")

    elif tipo == "Pizza":
        if aggregated:
            return px.pie(df, names="x", values="valor", title="Pizza — Agregado", hole=0.4)
        if y is None:
            counts = df[x].value_counts(dropna=False).rename_axis(x).reset_index(name="count")
            return px.pie(counts, names=x, values="count", title=f"Pizza — dist. {x}", hole=0.4)
        grouped = df.groupby(x, dropna=False)[y].sum().reset_index()
        return px.pie(grouped, names=x, values=y, title=f"Pizza — {y} por {x}", hole=0.4)

    elif tipo == "Histograma":
        return px.histogram(df, x=x, color=color, nbins=30, title=f"Histograma — {x}")

    elif tipo == "Scatter":
        if y is None:
            raise ValueError("Para Scatter, selecione Y numérico.")
        return px.scatter(df, x=x, y=y, color=color, title=f"Scatter — {y} vs {x}")

    else:
        raise ValueError("Tipo de gráfico não suportado.")
