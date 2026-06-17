# extrator_cnpj.py — v16
"""
Extrai empresas de qualquer recorte geográfico do banco SQLite.
v16: corrige type mismatch no filtro municipio (int vs string).
     municipio no banco é INTEGER — remove aspas para usar índice.

Para expandir para SP inteiro ou Brasil: edite apenas municipios_dim.csv.

Saída: data/raw/empresas_raw.csv
"""

import os
import sys
import time
import sqlite3
import pandas as pd
from config import (
    CODIGOS_RF_ALVO,
    MUNICIPIOS_RF,
    NATUREZAS_EXCLUIR,
    CNPJ_DB_PATH,
    DATA_RAW,
)

os.makedirs(DATA_RAW, exist_ok=True)

LARGURA = 70
SEP     = "━" * LARGURA


def verificar_banco():
    if not os.path.exists(CNPJ_DB_PATH):
        print(f"\n❌ Banco SQLite não encontrado: {CNPJ_DB_PATH}")
        sys.exit(1)
    tamanho_gb = os.path.getsize(CNPJ_DB_PATH) / 1_073_741_824
    print(f"  ✔  Banco SQLite encontrado ({tamanho_gb:.1f} GB)")


def detectar_tipo_municipio(conn: sqlite3.Connection) -> str:
    """
    Verifica se a coluna municipio é INTEGER ou TEXT no banco.
    Isso determina se o filtro usa aspas ou não — crítico para uso do índice.
    """
    cur = conn.execute("SELECT municipio FROM estabelecimento LIMIT 1")
    val = cur.fetchone()[0]
    return "int" if isinstance(val, int) else "str"


def extrair_empresas(conn: sqlite3.Connection) -> pd.DataFrame:
    """
    v16 — corrige type mismatch para garantir uso do índice composto.

    Fluxo:
      1. Detecta tipo da coluna municipio (int ou str)
      2. Constrói filtro correto (sem aspas para int, com aspas para str)
      3. Busca estabelecimentos filtrados → usa índice idx_estab_mun_sit
      4. Insere CNPJs em tabela temporária indexada
      5. JOIN único: empresas × temp
      6. JOIN único: socios × temp
      7. Merge pandas
    """

    conn.execute("PRAGMA cache_size = -128000;")
    conn.execute("PRAGMA temp_store = MEMORY;")
    conn.execute("PRAGMA journal_mode = OFF;")
    conn.execute("PRAGMA synchronous = OFF;")

    # Detecta tipo e constrói IN clause correta
    tipo_mun = detectar_tipo_municipio(conn)
    if tipo_mun == "int":
        # INTEGER no banco — sem aspas, índice funciona corretamente
        codigos_str = ", ".join(str(int(c)) for c in CODIGOS_RF_ALVO)
    else:
        # TEXT no banco — com aspas
        codigos_str = ", ".join(f"'{c}'" for c in CODIGOS_RF_ALVO)

    print(f"  ℹ️  Coluna municipio detectada como: {tipo_mun.upper()}")

    naturezas_excluir = ", ".join(f"'{n}'" for n in NATUREZAS_EXCLUIR)

    # ── Step 1: Estabelecimentos filtrados ───────────────────
    print(f"  1/4 Buscando estabelecimentos na região...")
    t = time.time()
    df_estab = pd.read_sql_query(f"""
        SELECT
            cnpj_basico,
            cnpj,
            cnae_fiscal            AS cnae_fiscal_principal,
            cnae_fiscal_secundaria,
            situacao_cadastral,
            data_inicio_atividades AS data_inicio_atividade,
            municipio,
            uf,
            bairro,
            cep,
            logradouro,
            numero,
            complemento,
            correio_eletronico,
            ddd1,
            telefone1
        FROM estabelecimento
        WHERE municipio IN ({codigos_str})
          AND situacao_cadastral = '02'
          AND matriz_filial = '1'
    """, conn)
    print(f"     ✔ {len(df_estab):,} estabelecimentos ({time.time()-t:.1f}s)")

    if df_estab.empty:
        return pd.DataFrame()

    # ── Step 2: Tabela temporária COM ÍNDICE ─────────────────
    print(f"  2/4 Criando tabela temporária indexada...")
    t = time.time()
    cnpjs_unicos = df_estab["cnpj_basico"].unique().tolist()

    conn.execute("DROP TABLE IF EXISTS temp_cnpjs")
    conn.execute("CREATE TEMP TABLE temp_cnpjs (cnpj_basico TEXT PRIMARY KEY)")
    conn.executemany(
        "INSERT OR IGNORE INTO temp_cnpjs VALUES (?)",
        [(c,) for c in cnpjs_unicos]
    )
    conn.commit()
    print(f"     ✔ {len(cnpjs_unicos):,} CNPJs indexados ({time.time()-t:.1f}s)")

    # ── Step 3: Empresas via JOIN duplo indexado ──────────────
    print(f"  3/4 Buscando dados de empresas...")
    t = time.time()
    df_empresas = pd.read_sql_query(f"""
        SELECT
            e.cnpj_basico,
            e.razao_social,
            e.natureza_juridica,
            e.qualificacao_responsavel,
            e.porte_empresa,
            e.capital_social
        FROM temp_cnpjs t
        INNER JOIN empresas e ON e.cnpj_basico = t.cnpj_basico
        WHERE e.natureza_juridica NOT IN ({naturezas_excluir})
    """, conn)
    print(f"     ✔ {len(df_empresas):,} empresas ({time.time()-t:.1f}s)")

    # ── Step 4: Sócios via JOIN duplo indexado ────────────────
    print(f"  4/4 Contando sócios...")
    t = time.time()
    df_socios = pd.read_sql_query("""
        SELECT s.cnpj_basico, COUNT(*) AS qtd_socios
        FROM temp_cnpjs t
        INNER JOIN socios s ON s.cnpj_basico = t.cnpj_basico
        GROUP BY s.cnpj_basico
    """, conn)
    print(f"     ✔ {len(df_socios):,} CNPJs com sócios ({time.time()-t:.1f}s)")

    # ── Merge em pandas ──────────────────────────────────────
    print(f"  ⚙️  Merge dos DataFrames...")
    t = time.time()
    df = df_estab.merge(df_empresas, on="cnpj_basico", how="inner")
    if not df_socios.empty:
        df = df.merge(df_socios, on="cnpj_basico", how="left")
        df["qtd_socios"] = df["qtd_socios"].fillna(0).astype(int)
    else:
        df["qtd_socios"] = 0
    print(f"     ✔ {len(df):,} registros finais ({time.time()-t:.1f}s)")

    return df


def mapear_municipios(df: pd.DataFrame) -> pd.DataFrame:
    inv = {v: k for k, v in MUNICIPIOS_RF.items()}
    # Aceita int ou str no municipio retornado pelo banco
    df["municipio_nome"] = df["municipio"].astype(str).str.strip().str.lstrip("0").map(
        {str(int(k)).lstrip("0") if k.isdigit() else k: v for k, v in inv.items()}
    ).fillna("OUTROS")
    # Fallback: tenta mapeamento direto
    sem_nome = df["municipio_nome"] == "OUTROS"
    if sem_nome.any():
        df.loc[sem_nome, "municipio_nome"] = df.loc[sem_nome, "municipio"].astype(str).map(inv).fillna("OUTROS")
    return df


def main():
    print(f"\n{SEP}")
    print("  🏗️  Extrator CNPJ — SQLite v16".center(LARGURA))
    print(SEP)
    print(f"\n  Municípios alvo ({len(MUNICIPIOS_RF)}):")
    for nome, cod in sorted(MUNICIPIOS_RF.items()):
        print(f"    {nome:<16} RF: {cod}")

    verificar_banco()
    print(f"\n  Conectando ao banco: {CNPJ_DB_PATH}\n")

    conn = sqlite3.connect(CNPJ_DB_PATH)
    inicio_total = time.time()

    try:
        df = extrair_empresas(conn)
        df = mapear_municipios(df)

        saida = os.path.join(DATA_RAW, "empresas_raw.csv")
        df.to_csv(saida, index=False, encoding="utf-8-sig")

        total = time.time() - inicio_total
        print(f"\n{SEP}")
        print(f"  ✅ Extração concluída em {total:.1f}s".center(LARGURA))
        print(SEP)
        print(f"\n  💾  Salvo em: {saida}")
        print(f"\n  📊 Por município:")
        print(df["municipio_nome"].value_counts().rename_axis(None).to_string())
        print()

    finally:
        conn.execute("DROP TABLE IF EXISTS temp_cnpjs")
        conn.close()


if __name__ == "__main__":
    main()