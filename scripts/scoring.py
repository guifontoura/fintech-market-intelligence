# scoring.py — v3
"""
Gera o score de propensão e os arquivos finais para dashboard.

Entrada:  data/processed/empresas_segmentadas.csv
          data/processed/setor_relevante.csv
Saída:    dashboards/leads_qualificados.csv
          dashboards/tam_por_municipio.csv
          dashboards/setores_ranking.csv

Critérios de score (0–100 pts):
  30 pts — situação cadastral ativa (código 02)
  20 pts — empresa com mais de 2 anos de operação
  25 pts — CNAE principal em setor de interesse da fintech
  15 pts — múltiplos sócios (empresa estruturada)
  10 pts — segmento High Ticket

Classificação:
  Hot Lead  81–100 pts  qualificado
  Quente    61–80  pts  qualificado
  Morno     31–60  pts  abaixo do corte
  Frio       0–30  pts  abaixo do corte
"""

import os
import time
import pandas as pd
from config import (
    PESOS_SCORE,
    CNAES_INTERESSE,
    CAPITAL_SOCIAL_HIGH_TICKET,
    DATA_PROCESSED,
    DASHBOARDS_DIR,
)

os.makedirs(DASHBOARDS_DIR, exist_ok=True)

# ⚠️  SUBSTITUIR pelos valores reais da fintech quando disponíveis.
LTV_MEDIO = {
    "High Ticket": 48_000,
    "Low Ticket":   3_600,
}

SCORE_CORTE = 61
LARGURA     = 62
SEP         = "━" * LARGURA
SEP_TAB     = "─" * 70


def calcular_score(df: pd.DataFrame, setores_relevantes: set) -> pd.DataFrame:
    df = df.copy()
    df = df[df["segmento"] != "Inativa"]

    def pontos(row):
        score = 0
        sit = str(row.get("situacao_cadastral", "")).strip()
        if sit in {"02", "2", "ATIVA", "ACTIVE"}:
            score += PESOS_SCORE["empresa_ativa"]
        try:
            anos = float(row.get("anos_operacao", 0) or 0)
        except (ValueError, TypeError):
            anos = 0
        if anos >= 2:
            score += PESOS_SCORE["tempo_operacao_anos"]
        secao = str(row.get("secao_cnae", ""))
        if secao in setores_relevantes:
            score += PESOS_SCORE["setor_relevante"]
        try:
            qtd = int(row.get("qtd_socios", 0) or 0)
        except (ValueError, TypeError):
            qtd = 0
        if qtd >= 2:
            score += PESOS_SCORE["multiplos_socios"]
        if row.get("segmento") == "High Ticket":
            score += PESOS_SCORE["high_ticket_proxy"]
        return score

    df["score"] = df.apply(pontos, axis=1)
    df["score_label"] = pd.cut(
        df["score"],
        bins=[0, 30, 60, 80, 100],
        labels=["Frio", "Morno", "Quente", "Hot Lead"],
        include_lowest=True,
    )

    df["score_ordem"] = df["score_label"].map({
        "Frio": 1,
        "Morno": 2,
        "Quente": 3,
        "Hot Lead": 4
    })

    df["faixa_score"] = pd.cut(
        df["score"],
        bins=[0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100],
        labels=[
            "00-10",
            "11-20",
            "21-30",
            "31-40",
            "41-50",
            "51-60",
            "61-70",
            "71-80",
            "81-90",
            "91-100"
        ],
        include_lowest=True
    )
    return df


def gerar_tam(df: pd.DataFrame) -> pd.DataFrame:
    tam = df.groupby(["municipio_nome", "segmento"]).agg(
        quantidade=("score", "count"),
        score_medio=("score", "mean"),
        hot_leads=("score_label", lambda x: (x == "Hot Lead").sum()),
    ).reset_index()
    tam["ltv_total_estimado"] = tam.apply(
        lambda r: r["quantidade"] * LTV_MEDIO.get(r["segmento"], 0), axis=1
    )
    tam["ltv_hot_leads_estimado"] = tam.apply(
        lambda r: r["hot_leads"] * LTV_MEDIO.get(r["segmento"], 0), axis=1
    )
    tam["score_medio"] = tam["score_medio"].round(1)
    ordem = (
        tam.groupby("municipio_nome")["quantidade"].sum()
        .sort_values(ascending=False).index.tolist()
    )
    tam["municipio_nome"] = pd.Categorical(
        tam["municipio_nome"], categories=ordem, ordered=True
    )
    return tam.sort_values(["municipio_nome", "segmento"]).reset_index(drop=True)


def main():
    inicio = time.time()

    path_emp   = os.path.join(DATA_PROCESSED, "empresas_segmentadas.csv")
    path_setor = os.path.join(DATA_PROCESSED, "setor_relevante.csv")

    if not os.path.exists(path_emp):
        print("⚠️  Execute primeiro: python etl.py")
        return

    print(f"\n🎯 Scoring — Propensão e Inteligência de Mercado...\n")

    df_emp = pd.read_csv(path_emp, dtype={"cnpj_completo": str, "cnpj_basico": str}, low_memory=False)
    setores_relevantes = set(CNAES_INTERESSE.keys())

    df_setor = pd.DataFrame()
    if os.path.exists(path_setor):
        df_setor = pd.read_csv(path_setor)

    print(f"  ✔  {len(df_emp):,} empresas pontuadas")
    print(f"     → High Ticket: Natureza SA/Ltda + Capital Social ≥ R$ {CAPITAL_SOCIAL_HIGH_TICKET:,.2f}")
    print(f"     → Low Ticket:  demais naturezas ou capital abaixo do limiar")
    print(f"     → LTV est. High Ticket: R$ {LTV_MEDIO['High Ticket']:,.0f}/ano "
          f"(~R$ {LTV_MEDIO['High Ticket']//12:,.0f}/mês)  ⚠️ placeholder")
    print(f"     → LTV est. Low Ticket:  R$ {LTV_MEDIO['Low Ticket']:,.0f}/ano "
          f"(~R$ {LTV_MEDIO['Low Ticket']//12:,.0f}/mês)  ⚠️ placeholder")

    df_scored = calcular_score(df_emp, setores_relevantes)
    distribuicao_score = df_scored.copy()

    dist = df_scored["score_label"].value_counts().reindex(
        ["Hot Lead", "Quente", "Morno", "Frio"]
    )
    qualificados = df_scored[df_scored["score"] >= SCORE_CORTE]

    leads = (
        df_scored[df_scored["score"] >= SCORE_CORTE]
        .sort_values("score", ascending=False)
        .drop_duplicates(subset="cnpj_basico", keep="first")
    )

    leads["ltv_estimado"] = leads["segmento"].map(LTV_MEDIO).fillna(0.0)

    print(f"\n  {'Score':<12} {'Qtd.':>8}    {'Faixa':<12}  Situação")
    print(f"  {'─'*56}")
    faixas = {
        "Hot Lead": "81–100 pts",
        "Quente":   "61–80  pts",
        "Morno":    "31–60  pts",
        "Frio":     " 0–30  pts",
    }
    for label, qtd in dist.items():
        situacao = "✔ qualificado" if label in {"Hot Lead", "Quente"} else "✗ abaixo do corte"
        print(f"  {label:<12} {qtd:>8,}    {faixas[label]:<12}  {situacao}")
    print(f"  {'─'*56}")
    print(f"  Leads qualificados (score ≥ {SCORE_CORTE}):   {len(leads):,} empresas\n")


    leads.to_csv(os.path.join(DASHBOARDS_DIR, "leads_qualificados.csv"),
                 index=False, encoding="utf-8-sig")
    tam = gerar_tam(df_scored)
    tam.to_csv(os.path.join(DASHBOARDS_DIR, "tam_por_municipio.csv"),
               index=False, encoding="utf-8-sig")
    distribuicao_score.to_csv(os.path.join(DASHBOARDS_DIR, "distribuicao_score.csv"),
                              index=False, encoding="utf-8-sig")
    if not df_setor.empty:
        df_setor.sort_values("n_empresas", ascending=False).to_csv(
            os.path.join(DASHBOARDS_DIR, "setores_ranking.csv"),
            index=False, encoding="utf-8-sig")

    tempo = time.time() - inicio

    print(f"  leads_qualificados.csv")
    print(f"  └─ {len(leads):,} empresas com score ≥ {SCORE_CORTE}, ordenadas por score decrescente\n")
    print(f"  tam_por_municipio.csv")
    print(f"  └─ TAM, LTV e Hot Leads por município e segmento\n")
    print(f"  setores_ranking.csv")
    print(f"  └─ setores ordenados por concentração de empresas na região\n")
    print(f"  💾  Arquivos salvos em: dashboards/")

    print(f"\n{SEP_TAB}")
    print(f"  📊 TAM por Município — Baixada Santista")
    print(f"{SEP_TAB}")
    print(f"  {'Município':<16} {'Segmento':<14} {'Qtd.':>8}  {'Hot Leads':>10}  {'LTV Total Est.':>16}")
    print(f"{SEP_TAB}")
    for _, row in tam.iterrows():
        print(
            f"  {row['municipio_nome']:<16} "
            f"{row['segmento']:<14} "
            f"{row['quantidade']:>8,}  "
            f"{row['hot_leads']:>10,}  "
            f"R$ {row['ltv_total_estimado']:>13,.0f}"
        )
    print(f"{SEP_TAB}\n")

    ht = tam[tam["segmento"] == "High Ticket"]
    lt = tam[tam["segmento"] == "Low Ticket"]
    total_ht   = ht["quantidade"].sum()
    ltv_ht     = ht["ltv_total_estimado"].sum()
    hot_ht     = ht["hot_leads"].sum()
    ltv_hot_ht = hot_ht * LTV_MEDIO["High Ticket"]
    total_lt   = lt["quantidade"].sum()
    ltv_lt     = lt["ltv_total_estimado"].sum()
    hot_lt     = lt["hot_leads"].sum()
    ltv_hot_lt = hot_lt * LTV_MEDIO["Low Ticket"]

    print(f"{SEP}")
    print(f"  📌 NÚMERO EXECUTIVO — Baixada Santista")
    print(f"{SEP}")
    print(f"  High Ticket ativas:    {total_ht:>8,}    LTV est.: R$ {ltv_ht:>16,.0f}")
    print(f"  Hot Leads HT:          {hot_ht:>8,}    LTV est.: R$ {ltv_hot_ht:>16,.0f}")
    print()
    print(f"  Low Ticket ativas:     {total_lt:>8,}    LTV est.: R$ {ltv_lt:>16,.0f}")
    print(f"  Hot Leads LT:          {hot_lt:>8,}    LTV est.: R$ {ltv_hot_lt:>16,.0f}")
    print(f"{SEP}")
    print(f"  ⚠️  LTV médio é placeholder — substitua em scoring.py linha ~17")
    print(f"  ⏱️  Tempo total: {tempo:.1f}s\n")

    # ── Salva dashboard.db para o Metabase ──────────────────
    import sqlite3
    db_path = os.path.join(DASHBOARDS_DIR, "dashboard.db")
    conn_dash = sqlite3.connect(db_path)
    leads.to_sql("leads_qualificados", conn_dash, if_exists="replace", index=False)
    tam.to_sql("tam_por_municipio", conn_dash, if_exists="replace", index=False)
    df_setor.to_sql("setores_ranking", conn_dash, if_exists="replace", index=False)
    dist_resumida = df_scored[[
        "cnpj_basico",
        "municipio_nome",
        "segmento",
        "score",
        "score_label",
        "score_ordem",
        "faixa_score",
        "setor_nome",
        "porte_empresa",
        "qtd_socios",
        "capital_social",
        "anos_operacao"
    ]].copy()
    dist_resumida.to_sql("distribuicao_score", conn_dash, if_exists="replace", index=False)
    conn_dash.close()
    print(f"  🗄️  dashboard.db atualizado: {db_path}")


if __name__ == "__main__":
    main()
