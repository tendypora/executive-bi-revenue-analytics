-- ============================================================================
-- CONSULTAS ANALÍTICAS DE BUSINESS INTELLIGENCE SOBRE O STAR SCHEMA
-- Tabelas: dim_clientes, dim_produtos, dim_calendario, fato_vendas
-- ============================================================================

-- 1. DRE Mensal: Evolução de MRR, Receita Bruta, Descontos, Impostos, Receita Líquida e Margem de Contribuição
SELECT c.ano,
       c.trimestre,
       f.competencia,
       COUNT(DISTINCT f.id_cliente)                                               AS clientes_ativos,
       ROUND(SUM(CAST(f.receita_bruta AS REAL)), 2)                               AS receita_bruta,
       ROUND(SUM(CAST(f.descontos AS REAL)), 2)                                   AS descontos_concedidos,
       ROUND(SUM(CAST(f.impostos AS REAL)), 2)                                    AS impostos_sobre_vendas,
       ROUND(SUM(CAST(f.receita_liquida AS REAL)), 2)                             AS receita_liquida,
       ROUND(SUM(CAST(f.margem_contribuicao AS REAL)), 2)                         AS margem_contribuicao,
       ROUND(SUM(CAST(f.margem_contribuicao AS REAL)) * 100.0
             / SUM(CAST(f.receita_liquida AS REAL)), 1)                           AS margem_pct,
       SUM(CAST(f.flag_churn AS INTEGER))                                         AS churn_logos
FROM fato_vendas f
JOIN dim_calendario c ON c.competencia = f.competencia
GROUP BY c.ano, c.trimestre, f.competencia
ORDER BY f.competencia;

-- 2. Unit Economics por Canal de Aquisição e Segmento (LTV, CAC e Payback em Meses)
WITH ltv_clientes AS (
    SELECT cl.id_cliente,
           cl.segmento,
           cl.canal_aquisicao,
           CAST(cl.custo_aquisicao_cac AS REAL)            AS cac,
           SUM(CAST(fv.margem_contribuicao AS REAL))       AS ltv_margem,
           AVG(CAST(fv.margem_contribuicao AS REAL))       AS margem_mensal_media,
           COUNT(fv.competencia)                           AS meses_retencao
    FROM dim_clientes cl
    JOIN fato_vendas fv ON fv.id_cliente = cl.id_cliente
    GROUP BY cl.id_cliente, cl.segmento, cl.canal_aquisicao, cl.custo_aquisicao_cac
)
SELECT canal_aquisicao,
       segmento,
       COUNT(*)                                            AS clientes,
       ROUND(AVG(cac), 2)                                  AS cac_medio,
       ROUND(AVG(ltv_margem), 2)                           AS ltv_medio,
       ROUND(AVG(ltv_margem) / AVG(cac), 2)                AS razao_ltv_cac,
       ROUND(AVG(cac / margem_mensal_media), 1)            AS payback_cac_meses
FROM ltv_clientes
GROUP BY canal_aquisicao, segmento
ORDER BY razao_ltv_cac DESC;

-- 3. Análise de Cohort (Retenção de Clientes por Safra de Entrada)
SELECT cl.safra_entrada,
       fv.competencia,
       COUNT(DISTINCT fv.id_cliente)                       AS clientes_retidos,
       ROUND(SUM(CAST(fv.receita_liquida AS REAL)), 2)     AS receita_safra
FROM dim_clientes cl
JOIN fato_vendas fv ON fv.id_cliente = cl.id_cliente
GROUP BY cl.safra_entrada, fv.competencia
ORDER BY cl.safra_entrada, fv.competencia;
