"""
app.py — Interface Streamlit para leitura e análise genérica de arquivos.

Funcionalidades:
- Upload (CSV, Excel, JSON)
- Leitura robusta (encodings/sep)
- Limpeza leve (remove Unnamed)
- Preview e download CSV (com fallback se faltar matplotlib)
- Estatísticas básicas
- Visualizações genéricas (barras, linha, pizza, histograma, scatter)
- Filtros (categóricos e numéricos), agregação (soma/média/contagem/mediana/máx/mín)
- Série temporal (dia/semana/mês/trimestre/ano) quando houver coluna de data
- Download do gráfico em PNG (requer kaleido)
"""

import io
import json
import pandas as pd
import streamlit as st
import plotly.io as pio
import plotly.express as px  # paletas

# módulos próprios
from utils import (
    infer_types,
    basic_stats,
    aggregate,
    detect_datetime_cols,
    time_aggregate,
)
from viz import plot_generic

# ==============================
# Configuração inicial
# ==============================
st.set_page_config(page_title="Leitor Genérico", layout="wide")

# Título
st.markdown(
    "<h1 style='text-align: center; color: #FFD700;'>📊 Leitor & Analisador de Dados</h1>",
    unsafe_allow_html=True,
)
st.markdown(
    "<p style='text-align: center; color: gray;'>Carregue CSV, Excel ou JSON e explore em segundos</p>",
    unsafe_allow_html=True,
)

# ==============================
# Upload
# ==============================
st.subheader("📂 Upload do Arquivo")
arquivo = st.file_uploader("Envie seu arquivo", type=["csv", "xlsx", "xls", "json"])

# ==============================
# Funções de leitura rápidas (inline)
# ==============================
def try_read_csv(file_bytes: bytes) -> pd.DataFrame:
    encodings = ["utf-8", "latin-1"]
    seps = [",", ";", "\t", "|"]
    for enc in encodings:
        for sep in seps:
            try:
                return pd.read_csv(io.BytesIO(file_bytes), encoding=enc, sep=sep)
            except Exception:
                continue
    raise ValueError("Não foi possível ler CSV (encoding/separador desconhecido).")


def try_read_excel(file_bytes: bytes) -> pd.DataFrame:
    xls = pd.ExcelFile(io.BytesIO(file_bytes))
    sheet = st.selectbox("Planilha do Excel", xls.sheet_names, index=0)
    return pd.read_excel(io.BytesIO(file_bytes), sheet_name=sheet)


def try_read_json(file_bytes: bytes) -> pd.DataFrame:
    raw = file_bytes.decode("utf-8", errors="ignore").strip()
    try:
        data = json.loads(raw)  # JSON array / objeto
        return pd.json_normalize(data)
    except Exception:
        rows = [json.loads(line) for line in raw.splitlines() if line.strip()]
        return pd.json_normalize(rows)

# ==============================
# Bloco Principal
# ==============================
if arquivo is not None:
    nome = arquivo.name.lower()
    file_bytes = arquivo.read()

    try:
        # Detecta extensão
        if nome.endswith(".csv"):
            df = try_read_csv(file_bytes)
        elif nome.endswith((".xlsx", ".xls")):
            df = try_read_excel(file_bytes)
        elif nome.endswith(".json"):
            df = try_read_json(file_bytes)
        else:
            st.error("Formato não suportado. Envie CSV, XLSX/XLS ou JSON.")
            st.stop()

        # Limpeza leve
        df = df.loc[:, ~df.columns.astype(str).str.match(r"^Unnamed")]

        # Info básica
        st.success("✅ Arquivo carregado com sucesso!")
        st.write(f"**Linhas:** {len(df):,} | **Colunas:** {df.shape[1]}")

        # Preview (com bordas mais fortes + fallback)
        n_preview = st.slider("Linhas para visualizar", 5, min(200, len(df)), 100)
        try:
            import matplotlib  # habilita background_gradient no Styler (requisito interno)

            styled_df = (
                df.head(n_preview)
                .style.background_gradient(cmap="Blues")
                .set_table_styles(
                    [
                        # cabeçalho mais escuro com borda
                        {"selector": "thead th",
                         "props": [("background-color", "#1f2937"),
                                   ("color", "white"),
                                   ("border", "2px solid #111")]}
                        ,
                        # células com bordas visíveis
                        {"selector": "tbody td",
                         "props": [("border", "1px solid #444")]}
                        ,
                        # hover leve nas linhas
                        {"selector": "tbody tr:hover td",
                         "props": [("background-color", "#e0f7fa !important")]}
                    ]
                )
            )
            st.dataframe(styled_df, use_container_width=True)
        except Exception:
            # sem matplotlib ou erro no Styler → mostra simples
            st.dataframe(df.head(n_preview), use_container_width=True)

        # Download dos dados normalizados (CSV)
        csv_out = df.to_csv(index=False).encode("utf-8")
        st.download_button(
            "⬇️ Baixar Dados em CSV",
            data=csv_out,
            file_name="dados_lidos.csv",
            mime="text/csv",
        )

        # ==============================
        # Abas de Análises
        # ==============================
        st.markdown("---")
        tab1, tab2 = st.tabs(["📊 Estatísticas", "📈 Gráficos"])

        # ---------- Estatísticas ----------
        with tab1:
            st.subheader("Resumo do Dataset")
            stats = basic_stats(df)

            colA, colB, colC, colD = st.columns(4)
            with colA:
                st.metric("Linhas", f"{stats['shape'][0]:,}")
            with colB:
                st.metric("Colunas", f"{stats['shape'][1]}")
            with colC:
                st.metric("Nulos (total)", f"{stats['nulls_total']:,}")
            with colD:
                st.metric("Memória (MB)", f"{stats['memory_mb']:.2f}")

            st.markdown("### Estatísticas Numéricas")
            if stats["describe_num"] is not None:
                st.dataframe(stats["describe_num"], use_container_width=True)
            else:
                st.info("Não há colunas numéricas para descrever.")

            st.markdown("### Top categorias (amostra)")
            for col, vc in stats["top_categories"].items():
                st.write(f"**{col}**")
                st.dataframe(vc.to_frame("contagem"), use_container_width=True)

        # ---------- Gráficos ----------
        with tab2:
            st.subheader("Gráficos Genéricos")

            types = infer_types(df)
            tipo = st.selectbox(
                "Tipo de gráfico", ["Barras", "Linha", "Pizza", "Histograma", "Scatter"]
            )

            # Paleta de cores (afeta os traces do Plotly)
            paletas = {
                "Padrão": None,
                "Vivas (Set1)": px.colors.qualitative.Set1,
                "Elegante (Viridis)": px.colors.sequential.Viridis,
                "Pastel": px.colors.qualitative.Pastel,
                "Plotly": px.colors.qualitative.Plotly,
            }
            paleta = st.selectbox("Paleta de cores", list(paletas.keys()), index=0)

            # definimos df_filt fora do expander pra sempre existir
            df_filt = df.copy()

            # ==== FILTROS (opcional) ====
            with st.expander("Filtros (opcional)"):
                cat_cols = types["text"]
                num_cols = types["numeric"]

                # categóricas (até 2)
                if cat_cols:
                    c1, c2 = st.columns(2)
                    with c1:
                        col_cat1 = st.selectbox(
                            "Filtrar por categórica 1", ["(nenhum)"] + cat_cols
                        )
                        if col_cat1 != "(nenhum)":
                            vals1 = st.multiselect(
                                "Valores",
                                sorted(df[col_cat1].astype(str).unique().tolist()),
                            )
                            if vals1:
                                df_filt = df_filt[
                                    df_filt[col_cat1].astype(str).isin(vals1)
                                ]
                    with c2:
                        col_cat2 = st.selectbox(
                            "Filtrar por categórica 2",
                            ["(nenhum)"] + [c for c in cat_cols if c != col_cat1],
                        )
                        if col_cat2 != "(nenhum)":
                            vals2 = st.multiselect(
                                "Valores ",
                                sorted(df[col_cat2].astype(str).unique().tolist()),
                            )
                            if vals2:
                                df_filt = df_filt[
                                    df_filt[col_cat2].astype(str).isin(vals2)
                                ]

                # numérico (range)
                if types["numeric"]:
                    c3, _ = st.columns(2)
                    with c3:
                        col_num = st.selectbox(
                            "Filtro numérico (range)", ["(nenhum)"] + types["numeric"]
                        )
                        if col_num != "(nenhum)":
                            mn, mx = float(df[col_num].min()), float(df[col_num].max())
                            r = st.slider("Intervalo", mn, mx, (mn, mx))
                            df_filt = df_filt[
                                (df_filt[col_num] >= r[0]) & (df_filt[col_num] <= r[1])
                            ]

            # ==== Série temporal (opcional) ====
            dt_cols = detect_datetime_cols(df_filt)
            use_time = False
            if tipo in ("Linha", "Barras") and dt_cols:
                use_time = st.checkbox(
                    "Tratar como série temporal (agrupar por período)", value=False
                )
                if use_time:
                    date_col = st.selectbox("Coluna de data", dt_cols)
                    freq_label = st.selectbox(
                        "Frequência", ["Dia", "Semana", "Mês", "Trimestre", "Ano"]
                    )
                    freq_map = {"Dia": "D", "Semana": "W", "Mês": "M", "Trimestre": "Q", "Ano": "Y"}
                    freq = freq_map[freq_label]

            # ==== Seleção de eixos ====
            x_choices = types["text"] + types["numeric"]
            y_choices = ["(nenhum)"] + types["numeric"]
            if tipo in ("Histograma", "Scatter"):
                x_choices = types["numeric"] or ["<sem numéricas>"]

            col1, col2, col3 = st.columns(3)
            with col1:
                x = st.selectbox("Eixo/Categoria (X)", x_choices)
            with col2:
                y = st.selectbox("Valor (Y) — numérico (quando aplicável)", y_choices)
            with col3:
                color = st.selectbox(
                    "Cor (opcional)", ["(nenhum)"] + types["text"] + types["numeric"]
                )

            # ==== Agregação + Top N ====
            agg_on = tipo in ("Barras", "Linha", "Pizza")
            topn_on = tipo in ("Barras", "Linha", "Pizza")

            if agg_on:
                how = st.selectbox(
                    "Agregação", ["soma", "média", "contagem", "mediana", "máximo", "mínimo"]
                )
            else:
                how = None

            if topn_on:
                topn = st.number_input(
                    "Top N (0 = todos)", min_value=0, max_value=100, value=0, step=1
                )
            else:
                topn = 0

            # ==== Botão ====
            if st.button("Gerar gráfico"):
                try:
                    y_val = None if y == "(nenhum)" else y
                    color_val = None if color == "(nenhum)" else color

                    if use_time:
                        # agrega por período temporal
                        data_agg = time_aggregate(
                            df_filt, date_col=date_col, y=y_val, how=how if agg_on else "soma", freq=freq
                        )
                        if topn_on and topn and topn > 0:
                            data_agg = data_agg.sort_values("valor", ascending=False).head(topn)
                        fig = plot_generic(
                            tipo, data_agg, x="x", y="valor", color=color_val, aggregated=True
                        )

                    elif agg_on:
                        # agrega por categoria numérica/texto
                        data_agg = aggregate(df_filt, x=x, y=y_val, how=how)
                        if topn and topn > 0:
                            data_agg = data_agg.sort_values("valor", ascending=False).head(topn)
                        fig = plot_generic(
                            tipo, data_agg, x="x", y="valor", color=color_val, aggregated=True
                        )

                    else:
                        # hist/scatter usam df filtrado direto
                        fig = plot_generic(
                            tipo, df_filt, x=x, y=y_val, color=color_val, aggregated=False
                        )

                    # aplica a paleta escolhida (se houver)
                    if paletas[paleta]:
                        fig.update_layout(colorway=paletas[paleta])

                    st.plotly_chart(fig, use_container_width=True)

                    # Exportar PNG (requer kaleido)
                    try:
                        png = fig.to_image(format="png", scale=2)  # precisa do kaleido
                        st.download_button(
                            "📥 Baixar gráfico (PNG)", data=png, file_name="grafico.png", mime="image/png"
                        )
                    except Exception as e_png:
                        st.caption(
                            f"Observação: para baixar PNG instale 'kaleido' (pip install kaleido). Detalhe: {e_png}"
                        )

                except Exception as e:
                    st.error(f"Falha ao gerar gráfico: {e}")

    except Exception as e:
        st.error(f"Falha ao ler o arquivo: {e}")
        st.info(
            "Dicas: verifique encoding/sep no CSV, planilha correta no Excel, ou se o JSON é array/NDJSON."
        )
else:
    st.info("Envie um arquivo para começar (CSV, Excel ou JSON).")

# Rodapé
st.markdown("<hr>", unsafe_allow_html=True)
st.markdown(
    "<p style='text-align:center; color:gray;'>Projeto acadêmico — Equipe batidão Uniruy</p>",
    unsafe_allow_html=True,
)
