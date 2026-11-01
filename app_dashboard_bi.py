"""Dashboard Interativo de Business Intelligence em Streamlit (Star Schema + Pandas/SQLite).

Para executar localmente:
    pip install streamlit pandas
    streamlit run app_dashboard_bi.py
"""
from __future__ import annotations

import pathlib
import sqlite3

import pandas as pd
import streamlit as st

RAIZ = pathlib.Path(__file__).resolve().parent
DB_PATH = RAIZ / "data_warehouse" / "bi_warehouse.db"

st.set_page_config(page_title="Executive BI & Revenue Analytics", page_icon="📊", layout="wide")
st.title("📊 Executive BI & Revenue Analytics — Star Schema Dashboard")
st.caption("Modelagem Dimensional (`dim_clientes`, `dim_produtos`, `dim_calendario`, `fato_vendas`) · DRE · LTV/CAC · Churn")

if not DB_PATH.exists():
    import pipeline_bi_analytics
    pipeline_bi_analytics.gerar_star_schema(RAIZ / "data_warehouse", seed=42)
    pipeline_bi_analytics.executar_consultas_sql_e_relatorios(RAIZ / "data_warehouse", RAIZ / "relatorios_bi")

con = sqlite3.connect(DB_PATH)
df = pd.read_sql_query("""
    SELECT f.competencia,
           c.segmento,
           c.canal_aquisicao,
           c.regiao,
           p.nome_produto,
           p.categoria,
           CAST(f.receita_bruta AS REAL) AS receita_bruta,
           CAST(f.receita_liquida AS REAL) AS receita_liquida,
           CAST(f.margem_contribuicao AS REAL) AS margem_contribuicao,
           CAST(f.flag_churn AS INTEGER) AS flag_churn
    FROM fato_vendas f
    JOIN dim_clientes c ON c.id_cliente = f.id_cliente
    JOIN dim_produtos p ON p.id_produto = f.id_produto
""", con)
con.close()

segmentos = st.sidebar.multiselect("Segmento", sorted(df["segmento"].unique()), default=sorted(df["segmento"].unique()))
canais = st.sidebar.multiselect("Canal de Aquisição", sorted(df["canal_aquisicao"].unique()), default=sorted(df["canal_aquisicao"].unique()))
df_f = df[df["segmento"].isin(segmentos) & df["canal_aquisicao"].isin(canais)]

c1, c2, c3, c4 = st.columns(4)
c1.metric("Receita Bruta", f"R$ {df_f['receita_bruta'].sum() / 1e6:.2f} mi")
c2.metric("Receita Líquida", f"R$ {df_f['receita_liquida'].sum() / 1e6:.2f} mi")
c3.metric("Margem de Contribuição", f"R$ {df_f['margem_contribuicao'].sum() / 1e6:.2f} mi")
c4.metric("Cancelamentos (Churn)", f"{int(df_f['flag_churn'].sum())} logos")

st.subheader("Evolução Mensal de Receita Líquida e Margem de Contribuição (DRE)")
evol = df_f.groupby("competencia")[["receita_liquida", "margem_contribuicao"]].sum()
st.line_chart(evol)

col_a, col_b = st.columns(2)
with col_a:
    st.subheader("Receita Líquida por Produto")
    st.bar_chart(df_f.groupby("nome_produto")["receita_liquida"].sum())
with col_b:
    st.subheader("Receita Líquida por Canal de Aquisição")
    st.bar_chart(df_f.groupby("canal_aquisicao")["receita_liquida"].sum())
