# etl.py — v6
"""
ETL — Limpeza, Segmentação e Enriquecimento dos dados brutos.

Entrada:  data/raw/empresas_raw.csv
          data/raw/caged_saldo_setores.csv
Saída:    data/processed/empresas_segmentadas.csv
          data/processed/setor_relevante.csv

Critério High Ticket (qualquer um):
  A) Natureza SA/Ltda + Capital Social ≥ R$500.000
  B) Porte RF = 5 (demais / médio-grande)
     Nota: SQLite armazena sem zero à esquerda ("5" não "05")
"""

import os
import time
import pandas as pd
from config import (
    NATUREZA_LOW_TICKET,
    NATUREZA_HIGH_TICKET,
    NATUREZAS_EXCLUIR,
    CAPITAL_SOCIAL_HIGH_TICKET,
    PORTE_HIGH_TICKET,
    CNAES_INTERESSE,
    DATA_RAW,
    DATA_PROCESSED,
)

os.makedirs(DATA_PROCESSED, exist_ok=True)

LARGURA = 56
SEP     = "━" * LARGURA
SEP_FIN = "─" * 38

SITUACOES_ATIVAS = {"02", "2", "ATIVA", "ACTIVE"}

COLUNAS_REMOVER = [
    "motivo_situacao_cadastral",
    "nome_cidade_exterior", "pais",
    "identificador_matriz_filial",
    "situacao_especial", "data_situacao_especial",
    "ddd2", "telefone2", "ddd_fax", "fax",
]

COLUNAS_CNPJ_AUX = ["cnpj_ordem", "cnpj_dv"]

CNAE_PARA_SECAO = {
    **{str(i).zfill(2): "A" for i in range(1,  4)},
    **{str(i).zfill(2): "B" for i in range(5,  10)},
    **{str(i).zfill(2): "C" for i in range(10, 34)},
    "35": "D",
    **{str(i).zfill(2): "E" for i in range(36, 40)},
    "41": "F", "42": "F", "43": "F",
    **{str(i).zfill(2): "G" for i in range(45, 48)},
    **{str(i).zfill(2): "H" for i in range(49, 54)},
    "55": "I", "56": "I",
    **{str(i).zfill(2): "J" for i in range(58, 64)},
    **{str(i).zfill(2): "K" for i in range(64, 67)},
    "68": "L",
    **{str(i).zfill(2): "M" for i in range(69, 76)},
    **{str(i).zfill(2): "N" for i in range(77, 83)},
    "84": "O", "85": "P",
    **{str(i).zfill(2): "Q" for i in range(86, 89)},
    **{str(i).zfill(2): "R" for i in range(90, 94)},
    **{str(i).zfill(2): "S" for i in range(94, 97)},
    "97": "T", "99": "U",
}


# ─────────────────────────────────────────────
# ETAPA 1 — LIMPEZA
# ─────────────────────────────────────────────

def limpar_empresas(df: pd.DataFrame) -> tuple[pd.DataFrame, int, int]:
    original = len(df)
    df.columns = df.columns.str.lower().str.strip()

    # Remove naturezas irrelevantes (condomínios, fundações, órgãos públicos)
    # SQLite pode ter com ou sem zeros à esquerda — normaliza para string
    if "natureza_juridica" in df.columns:
        df["natureza_juridica"] = df["natureza_juridica"].astype(str).str.strip()
        df = df[~df["natureza_juridica"].isin(NATUREZAS_EXCLUIR)]

    cols_remover = [c for c in COLUNAS_REMOVER if c in df.columns]
    df = df.drop(columns=cols_remover)

    if "cnpj_basico" in df.columns:
        df = df.dropna(subset=["cnpj_basico"])

    # cnpj_completo — usa coluna 'cnpj' do SQLite diretamente (já formatado)
    if "cnpj" in df.columns:
        df = df.rename(columns={"cnpj": "cnpj_completo"})
        # Garante que vire string e aplica o zfill de 14 dígitos caso o SQLite tenha retornado número
        df["cnpj_completo"] = df["cnpj_completo"].astype(str).str.split('.').str[0].str.zfill(14)

    elif all(c in df.columns for c in ["cnpj_basico", "cnpj_ordem", "cnpj_dv"]):
        df["cnpj_completo"] = (
                df["cnpj_basico"].astype(str).str.split('.').str[0].str.zfill(8)
                + df["cnpj_ordem"].astype(str).str.split('.').str[0].str.zfill(4)
                + df["cnpj_dv"].astype(str).str.split('.').str[0].str.zfill(2)
        )

    # Data de abertura → anos de operação
    data_col = next((c for c in df.columns if "data_inicio" in c or "abertura" in c), None)
    if data_col:
        df[data_col] = pd.to_datetime(df[data_col], format="%Y%m%d", errors="coerce")
        df["anos_operacao"] = (pd.Timestamp.now() - df[data_col]).dt.days / 365
    else:
        df["anos_operacao"] = None

    # Capital social → float limpo (SQLite já vem como float, ZIPs como string)
    if "capital_social" in df.columns:
        df["capital_social"] = pd.to_numeric(
            df["capital_social"].astype(str).str.replace(",", "."),
            errors="coerce",
        ).fillna(0.0).round(2)
    else:
        df["capital_social"] = 0.0

    # Normaliza códigos numéricos → string sem zeros à esquerda (padrão SQLite)
    for col in ["natureza_juridica", "porte_empresa"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").astype("Int64").astype(str)
            df[col] = df[col].replace("<NA>", "")

    # DDD e telefone → Int64 nullable
    for col in ["ddd1", "telefone1"]:
        if col in df.columns:
            df[col] = pd.to_numeric(
                df[col].astype(str).str.replace(r"\.0$", "", regex=True),
                errors="coerce"
            ).astype("Int64")

    if "municipio_nome" not in df.columns:
        df["municipio_nome"] = "Desconhecido"

    return df, original, len(df)


# ─────────────────────────────────────────────
# ETAPA 2 — SEGMENTAÇÃO
# ─────────────────────────────────────────────

def segmentar_empresas(df: pd.DataFrame) -> pd.DataFrame:
    def classificar(row):
        nat      = str(row.get("natureza_juridica", "")).strip()
        capital  = float(row.get("capital_social",   0) or 0)
        situacao = str(row.get("situacao_cadastral",  "")).strip().upper()
        porte    = str(row.get("porte_empresa",       "")).strip()

        if situacao not in SITUACOES_ATIVAS:
            return "Inativa"

        # Critério A — natureza + capital
        if nat in NATUREZA_HIGH_TICKET and capital >= CAPITAL_SOCIAL_HIGH_TICKET:
            return "High Ticket"

        # Critério B — porte RF (5 = demais/médio-grande, sem zero à esquerda)
        if porte in PORTE_HIGH_TICKET:
            return "High Ticket"

        if nat in NATUREZA_LOW_TICKET:
            return "Low Ticket"

        return "Low Ticket"

    df["segmento"] = df.apply(classificar, axis=1)
    return df


def gerar_resumo(df: pd.DataFrame) -> pd.DataFrame:
    ativas = df[df["segmento"] != "Inativa"]
    resumo = (
        ativas.groupby(["municipio_nome", "segmento"])
        .size()
        .reset_index(name="quantidade")
    )
    ordem = (
        ativas.groupby("municipio_nome").size()
        .sort_values(ascending=False).index.tolist()
    )
    resumo["municipio_nome"] = pd.Categorical(
        resumo["municipio_nome"], categories=ordem, ordered=True
    )
    return resumo.sort_values(["municipio_nome", "segmento"]).reset_index(drop=True)


# ─────────────────────────────────────────────
# ETAPA 3 — ENRIQUECIMENTO SETORIAL
# ─────────────────────────────────────────────

def enriquecer_com_setor(df: pd.DataFrame) -> pd.DataFrame:
    # Aceita tanto 'cnae_fiscal_principal' (ZIPs) quanto 'cnae_fiscal' (SQLite)
    cnae_col = next(
        (c for c in df.columns if c in {"cnae_fiscal_principal", "cnae_fiscal"}),
        None
    )
    if cnae_col:
        df["secao_cnae"] = df[cnae_col].astype(str).str[:2].map(CNAE_PARA_SECAO)
        df["setor_nome"] = df["secao_cnae"].map(CNAES_INTERESSE).fillna("Outros")
    return df


def limpar_cempre(df: pd.DataFrame) -> pd.DataFrame:
    df.columns = df.columns.str.lower().str.strip()
    if "n_empresas" in df.columns:
        df["n_empresas"] = pd.to_numeric(df["n_empresas"], errors="coerce").fillna(0)
    if "secao_nome" in df.columns:
        df = df[df["secao_nome"] != "Total"]
    return df


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

def main():
    inicio = time.time()
    print(f"\n🔄 ETL — Limpeza, Segmentação e Enriquecimento...\n")

    path_emp = os.path.join(DATA_RAW, "empresas_raw.csv")
    if not os.path.exists(path_emp):
        print(f"  ⚠️  empresas_raw.csv não encontrado.")
        print(f"      Execute primeiro: python extrator_cnpj.py")
        return

    df_emp, original, validos = limpar_empresas(
        pd.read_csv(path_emp, dtype=str, low_memory=False)
    )
    descartados = original - validos
    removidos_natureza = original - validos - descartados if descartados == 0 else 0

    print(f"  ✔  {original:,} registros carregados → {validos:,} válidos ({descartados:,} descartados)")
    print(f"  🧹  Campos tratados: CNPJ, data de abertura, capital social, DDD")
    print(f"  🗑️  Naturezas excluídas: condomínios, fundações, órgãos públicos")

    df_emp = segmentar_empresas(df_emp)

    # Diagnóstico de segmentação
    ht = (df_emp["segmento"] == "High Ticket").sum()
    lt = (df_emp["segmento"] == "Low Ticket").sum()
    print(f"  🏷  Segmentação: {ht:,} High Ticket | {lt:,} Low Ticket")
    print(f"      Critério A: Natureza SA/Ltda + Capital ≥ R${CAPITAL_SOCIAL_HIGH_TICKET:,.0f}")
    print(f"      Critério B: Porte RF = 5 (médio-grande)")

    df_emp = enriquecer_com_setor(df_emp)
    print(f"  📑  Enriquecimento: Seção CNAE mapeada para todos os registros")

    saida_emp = os.path.join(DATA_PROCESSED, "empresas_segmentadas.csv")
    df_emp.to_csv(saida_emp, index=False, encoding="utf-8-sig")

    path_caged = os.path.join(DATA_RAW, "caged_saldo_setores.csv")
    saida_c = None
    if os.path.exists(path_caged):
        df_c = limpar_cempre(pd.read_csv(path_caged, low_memory=False))
        saida_c = os.path.join(DATA_PROCESSED, "setor_relevante.csv")
        df_c.to_csv(saida_c, index=False, encoding="utf-8-sig")

    tempo = time.time() - inicio

    print(f"\n{SEP}")
    print(f"  ✅ ETL finalizado com sucesso")
    print(f"  ⏱️  Tempo total: {tempo:.1f}s")
    print(f"{SEP}\n")

    print(f"  empresas_segmentadas.csv")
    print(f"  └─ {validos:,} empresas com segmento, setor, cnpj_completo,")
    print(f"     anos de operação e quantidade de sócios")
    if saida_c:
        print(f"\n  setor_relevante.csv")
        print(f"  └─ Ranking de empresas por setor e município")
    print(f"\n  💾  Arquivos salvos em: data/processed/")

    resumo = gerar_resumo(df_emp)
    print(f"\n{SEP_FIN}")
    print(f"  {'Município':<20} {'Segmento':<14} {'Qtd.':>8}")
    print(f"{SEP_FIN}")
    for _, row in resumo.iterrows():
        print(f"  {row['municipio_nome']:<20} {row['segmento']:<14} {row['quantidade']:>8,}")
    print(f"{SEP_FIN}\n")


if __name__ == "__main__":
    main()