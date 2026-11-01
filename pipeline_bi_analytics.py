#!/usr/bin/env python3
"""Pipeline de Business Intelligence (Star Schema), Análise de Receita, Churn/Cohort e Relatórios Executivos.

Execução:
    python pipeline_bi_analytics.py

Entregáveis gerados automaticamente:
  1. Modelagem Dimensional Star Schema em CSV (pronta para Power BI / Tableau) e banco SQLite (`bi_warehouse.db`):
     - data_warehouse/dim_calendario.csv
     - data_warehouse/dim_clientes.csv
     - data_warehouse/dim_produtos.csv
     - data_warehouse/fato_vendas.csv
  2. Consultas SQL Analíticas sobre o Star Schema (Receita, DRE/Margem, LTV, CAC, Churn e Cohort).
  3. Relatórios Executivos Automatizados:
     - relatorios_bi/painel_executivo_dre_e_kpis.xlsx
     - relatorios_bi/relatorio_comite_comercial_bi.pdf
"""
from __future__ import annotations

import csv
import datetime as dt
import pathlib
import random
import sqlite3
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

RAIZ = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ / "src"))

from pdf_simples import escrever_pdf  # noqa: E402
from xlsx_simples import escrever_xlsx  # noqa: E402

SEGMENTOS = ["Enterprise", "Mid-Market", "SMB"]
CANAIS = ["Inbound Marketing", "Outbound SDR", "Parceiros Cloud", "Indicação Executiva"]
REGIOES = ["Sudeste", "Sul", "Nordeste", "Centro-Oeste"]
PRODUTOS = [
    ("PRD-01", "Plataforma Data Analytics Pro", "SaaS Analytics", 4200.00, 0.82),
    ("PRD-02", "Motor de Automação RPA Cloud", "Automação & RPA", 3100.00, 0.78),
    ("PRD-03", "Agente Inteligente IA & Copilot", "Inteligência Artificial", 5800.00, 0.75),
    ("PRD-04", "Conector Enterprise ERP/CRM", "Integração & Dados", 1900.00, 0.85),
    ("PRD-05", "Pacote Governança & Cloud FinOps", "Cloud & FinOps", 3600.00, 0.80),
]


def gerar_star_schema(pasta_dw: pathlib.Path, seed: int = 42) -> tuple[list[dict], list[dict], list[dict]]:
    rng = random.Random(seed)
    pasta_dw.mkdir(parents=True, exist_ok=True)

    # 1. dim_produtos
    dim_produtos = []
    for pid, nome, cat, preco, margem_bruta in PRODUTOS:
        dim_produtos.append({
            "id_produto": pid,
            "nome_produto": nome,
            "categoria": cat,
            "preco_mensal_lista": preco,
            "margem_bruta_padrao": margem_bruta,
        })

    # 2. dim_calendario (2025-01 a 2026-10)
    dim_calendario = []
    competencias = []
    for ano in (2025, 2026):
        for mes in range(1, 13):
            if ano == 2026 and mes > 10:
                continue
            comp = f"{ano}-{mes:02d}"
            competencias.append(comp)
            trimestre = f"T{(mes - 1) // 3 + 1}/{ano}"
            dim_calendario.append({
                "competencia": comp,
                "ano": ano,
                "mes": mes,
                "trimestre": trimestre,
                "semestre": f"S{1 if mes <= 6 else 2}/{ano}",
            })

    # 3. dim_clientes (320 clientes B2B)
    dim_clientes = []
    cac_por_canal = {
        "Inbound Marketing": 3800.0,
        "Outbound SDR": 6400.0,
        "Parceiros Cloud": 4500.0,
        "Indicação Executiva": 2900.0,
    }
    for i in range(1, 321):
        cid = f"CLI-{i:04d}"
        seg = rng.choices(SEGMENTOS, weights=[0.22, 0.43, 0.35])[0]
        canal = rng.choices(CANAIS, weights=[0.38, 0.32, 0.18, 0.12])[0]
        regiao = rng.choices(REGIOES, weights=[0.54, 0.22, 0.14, 0.10])[0]
        safra_idx = rng.randint(0, len(competencias) - 4)
        safra = competencias[safra_idx]
        cac = round(cac_por_canal[canal] * rng.uniform(0.88, 1.15), 2)
        dim_clientes.append({
            "id_cliente": cid,
            "segmento": seg,
            "canal_aquisicao": canal,
            "regiao": regiao,
            "safra_entrada": safra,
            "custo_aquisicao_cac": cac,
        })

    # 4. fato_vendas (recorrência mensal + expansão + churn realista)
    fato_vendas = []
    id_transacao = 1
    for cli in dim_clientes:
        idx_inicio = competencias.index(cli["safra_entrada"])
        prod = rng.choice(dim_produtos)
        licencas = {"Enterprise": rng.randint(3, 8), "Mid-Market": rng.randint(2, 4), "SMB": 1}[cli["segmento"]]
        desconto_pct = rng.choice([0.0, 0.05, 0.10, 0.15])
        prob_churn_mensal = {"Enterprise": 0.012, "Mid-Market": 0.024, "SMB": 0.042}[cli["segmento"]]
        ativo = True

        for comp in competencias[idx_inicio:]:
            if not ativo:
                break
            receita_bruta = round(prod["preco_mensal_lista"] * licencas, 2)
            desconto_val = round(receita_bruta * desconto_pct, 2)
            impostos_val = round((receita_bruta - desconto_val) * 0.1125, 2)
            receita_liquida = round(receita_bruta - desconto_val - impostos_val, 2)
            custo_cloud_cogs = round(receita_liquida * (1.0 - prod["margem_bruta_padrao"]), 2)
            margem_contribuicao = round(receita_liquida - custo_cloud_cogs, 2)

            churn_no_mes = 1 if (comp != cli["safra_entrada"] and rng.random() < prob_churn_mensal) else 0
            if churn_no_mes:
                ativo = False

            fato_vendas.append({
                "id_transacao": f"TRX-{id_transacao:05d}",
                "competencia": comp,
                "id_cliente": cli["id_cliente"],
                "id_produto": prod["id_produto"],
                "licencas": licencas,
                "receita_bruta": receita_bruta,
                "descontos": desconto_val,
                "impostos": impostos_val,
                "receita_liquida": receita_liquida,
                "custo_cogs": custo_cloud_cogs,
                "margem_contribuicao": margem_contribuicao,
                "flag_churn": churn_no_mes,
            })
            id_transacao += 1

    def salvar_csv(nome: str, registros: list[dict]) -> None:
        caminho = pasta_dw / nome
        with caminho.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(registros[0].keys()))
            w.writeheader()
            w.writerows(registros)

    salvar_csv("dim_produtos.csv", dim_produtos)
    salvar_csv("dim_calendario.csv", dim_calendario)
    salvar_csv("dim_clientes.csv", dim_clientes)
    salvar_csv("fato_vendas.csv", fato_vendas)
    return dim_clientes, dim_produtos, fato_vendas


def executar_consultas_sql_e_relatorios(pasta_dw: pathlib.Path, pasta_rel: pathlib.Path) -> dict:
    db_path = pasta_dw / "bi_warehouse.db"
    if db_path.exists():
        db_path.unlink()

    con = sqlite3.connect(db_path)
    cur = con.cursor()

    for tabela in ("dim_produtos", "dim_calendario", "dim_clientes", "fato_vendas"):
        with (pasta_dw / f"{tabela}.csv").open(encoding="utf-8") as f:
            leitor = list(csv.reader(f))
            colunas = leitor[0]
            placeholders = ",".join("?" for _ in colunas)
            cur.execute(f"CREATE TABLE {tabela} ({','.join(colunas)})")
            cur.executemany(f"INSERT INTO {tabela} VALUES ({placeholders})", leitor[1:])
    con.commit()

    # Consulta 1: DRE Mensal e Evolução de MRR / Margem
    dre_mensal = cur.execute("""
        SELECT f.competencia,
               COUNT(DISTINCT f.id_cliente) AS clientes_ativos,
               ROUND(SUM(CAST(f.receita_bruta AS REAL)), 2) AS receita_bruta,
               ROUND(SUM(CAST(f.receita_liquida AS REAL)), 2) AS receita_liquida,
               ROUND(SUM(CAST(f.margem_contribuicao AS REAL)), 2) AS margem_contribuicao,
               ROUND(SUM(CAST(f.margem_contribuicao AS REAL)) * 100.0 / SUM(CAST(f.receita_liquida AS REAL)), 1) AS margem_pct,
               SUM(CAST(f.flag_churn AS INTEGER)) AS cancelamentos
        FROM fato_vendas f
        GROUP BY f.competencia
        ORDER BY f.competencia
    """).fetchall()

    # Consulta 2: Performance por Segmento & Unit Economics (LTV, CAC, LTV/CAC)
    unit_economics = cur.execute("""
        WITH receita_por_cliente AS (
            SELECT c.id_cliente,
                   c.segmento,
                   c.canal_aquisicao,
                   CAST(c.custo_aquisicao_cac AS REAL) AS cac,
                   SUM(CAST(f.margem_contribuicao AS REAL)) AS margem_acumulada_ltv,
                   COUNT(f.competencia) AS meses_retido,
                   MAX(CAST(f.flag_churn AS INTEGER)) AS sofreu_churn
            FROM dim_clientes c
            JOIN fato_vendas f ON f.id_cliente = c.id_cliente
            GROUP BY c.id_cliente, c.segmento, c.canal_aquisicao, c.custo_aquisicao_cac
        )
        SELECT segmento,
               COUNT(*) AS total_clientes,
               ROUND(AVG(cac), 2) AS cac_medio,
               ROUND(AVG(margem_acumulada_ltv), 2) AS ltv_realizado_medio,
               ROUND(AVG(margem_acumulada_ltv) / AVG(cac), 2) AS razao_ltv_cac,
               ROUND(SUM(sofreu_churn) * 100.0 / COUNT(*), 1) AS taxa_churn_acumulada_pct
        FROM receita_por_cliente
        GROUP BY segmento
        ORDER BY razao_ltv_cac DESC
    """).fetchall()

    # Consulta 3: Receita e Margem por Produto
    por_produto = cur.execute("""
        SELECT p.id_produto,
               p.nome_produto,
               p.categoria,
               ROUND(SUM(CAST(f.receita_liquida AS REAL)), 2) AS receita_liquida_total,
               ROUND(SUM(CAST(f.margem_contribuicao AS REAL)), 2) AS margem_total
        FROM fato_vendas f
        JOIN dim_produtos p ON p.id_produto = f.id_produto
        GROUP BY p.id_produto, p.nome_produto, p.categoria
        ORDER BY receita_liquida_total DESC
    """).fetchall()
    con.close()

    pasta_rel.mkdir(parents=True, exist_ok=True)
    linhas_xlsx = [[
        "Competência", "Clientes Ativos", "Receita Bruta (R$)",
        "Receita Líquida (R$)", "Margem de Contribuição (R$)", "Margem (%)", "Churned Logos"
    ]] + [list(r) for r in dre_mensal]

    caminho_xlsx = pasta_rel / "painel_executivo_dre_e_kpis.xlsx"
    escrever_xlsx(caminho_xlsx, linhas_xlsx, aba="DRE_Mensal_BI")

    rec_total = sum(r[3] for r in dre_mensal)
    margem_total = sum(r[4] for r in dre_mensal)

    blocos_pdf = [
        ("titulo", "Executive BI & Revenue Analytics - Relatorio de Performance Comercial e DRE"),
        ("subtitulo", "Modelagem Star Schema (SQL + Python) | Indicadores de Receita, LTV/CAC, Churn e Margem"),
        ("espaco", ""),
        ("subtitulo", "1. DESTAQUES EXECUTIVOS ACUMULADOS (2025-2026)"),
        ("normal", f"Receita Liquida Acumulada: R$ {rec_total / 1e6:.2f} milhoes | Margem de Contribuicao: R$ {margem_total / 1e6:.2f} milhoes."),
        ("normal", f"Base Total Modelada: 320 Clientes B2B | {sum(r[1] for r in dre_mensal[-1:])} Clientes Ativos em Outubro/2026."),
        ("espaco", ""),
        ("subtitulo", "2. UNIT ECONOMICS POR SEGMENTO (LTV, CAC E CHURN)"),
    ]
    for seg, tot, cac, ltv, ratio, ch_pct in unit_economics:
        blocos_pdf.append((
            "normal",
            f"Segmento {seg:<10} | Clientes: {tot:3d} | CAC Medio: R$ {cac:7.2f} | LTV Medio: R$ {ltv:9.2f} | LTV/CAC: {ratio:4.1f}x | Churn: {ch_pct:4.1f}%"
        ))

    blocos_pdf.extend([
        ("espaco", ""),
        ("subtitulo", "3. PERFORMANCE POR LINHA DE PRODUTO (TOP 5)"),
    ])
    for pid, nome, cat, rec_p, marg_p in por_produto:
        blocos_pdf.append((
            "normal",
            f"{pid} - {nome} ({cat}) | Receita Liquida: R$ {rec_p / 1e6:.2f} mi | Margem: R$ {marg_p / 1e6:.2f} mi"
        ))

    caminho_pdf = pasta_rel / "relatorio_comite_comercial_bi.pdf"
    escrever_pdf(caminho_pdf, blocos_pdf)

    return {
        "transacoes_fato_vendas": sum(1 for _ in (pasta_dw / "fato_vendas.csv").open(encoding="utf-8")) - 1,
        "receita_liquida_milhoes": round(rec_total / 1e6, 2),
        "margem_contribuicao_milhoes": round(margem_total / 1e6, 2),
        "xlsx": str(caminho_xlsx),
        "pdf": str(caminho_pdf),
    }


if __name__ == "__main__":
    dw = RAIZ / "data_warehouse"
    rel = RAIZ / "relatorios_bi"
    gerar_star_schema(dw, seed=42)
    resumo = executar_consultas_sql_e_relatorios(dw, rel)
    print("Pipeline de BI & Star Schema concluído com sucesso!")
    for k, v in resumo.items():
        print(f"  {k:<28}: {v}")
