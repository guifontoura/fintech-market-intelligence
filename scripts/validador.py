# validador.py — v2
"""
Valida os dados gerados pelo pipeline comparando com benchmarks oficiais.
Execute após o scoring.py para garantir qualidade antes de apresentar.

Benchmarks: SEBRAE 2024, RAIS 2023.
"""

import os
import pandas as pd
from config import DATA_RAW, DATA_PROCESSED, DASHBOARDS_DIR

LARGURA = 62
SEP     = "━" * LARGURA
SEP_FIN = "─" * 62

BENCHMARKS_EMPRESAS = {
    "SANTOS":       {"min": 70_000,  "max": 115_000, "fonte": "SEBRAE 2024"},
    "SAO VICENTE":  {"min": 35_000,  "max":  65_000, "fonte": "SEBRAE 2024"},
    "GUARUJA":      {"min": 30_000,  "max":  55_000, "fonte": "SEBRAE 2024"},
    "PRAIA GRANDE": {"min": 40_000,  "max":  80_000, "fonte": "SEBRAE 2024"},
    "CUBATAO":      {"min": 10_000,  "max":  22_000, "fonte": "SEBRAE 2024"},
    "ITANHAEM":     {"min": 10_000,  "max":  22_000, "fonte": "SEBRAE 2024"},
    "BERTIOGA":     {"min":  7_000,  "max":  18_000, "fonte": "SEBRAE 2024"},
    "PERUIBE":      {"min":  7_000,  "max":  18_000, "fonte": "SEBRAE 2024"},
    "MONGAGUA":     {"min":  6_000,  "max":  16_000, "fonte": "SEBRAE 2024"},
}

# Intervalo ajustado para a Baixada Santista — região com menor concentração
# de médias/grandes empresas vs média nacional (referência: RAIS 2023 SP)
PCT_HIGH_TICKET_MIN = 2.0   # % mínimo esperado de High Ticket
PCT_HIGH_TICKET_MAX = 25.0  # % máximo esperado de High Ticket


def checar_arquivo(caminho: str, nome: str) -> bool:
    if not os.path.exists(caminho):
        print(f"  ❌ {nome} — não encontrado: {caminho}")
        return False
    size_mb = os.path.getsize(caminho) / 1_048_576
    print(f"  ✔  {nome:<35} {size_mb:.1f} MB")
    return True


def validar_volumes(df: pd.DataFrame) -> list[str]:
    avisos = []
    contagem = df.groupby("municipio_nome").size()
    for municipio, ref in BENCHMARKS_EMPRESAS.items():
        total = contagem.get(municipio, 0)
        if total == 0:
            avisos.append(f"⚠️  {municipio}: sem registros")
        elif total < ref["min"]:
            avisos.append(
                f"⚠️  {municipio}: {total:,} empresas — abaixo do esperado "
                f"({ref['min']:,}–{ref['max']:,} | {ref['fonte']})"
            )
        elif total > ref["max"]:
            avisos.append(
                f"⚠️  {municipio}: {total:,} empresas — acima do esperado "
                f"({ref['min']:,}–{ref['max']:,} | {ref['fonte']})"
            )
    return avisos


def validar_segmentacao(df: pd.DataFrame) -> list[str]:
    avisos = []
    ativas = df[df["segmento"] != "Inativa"]
    if len(ativas) == 0:
        return ["❌ Nenhuma empresa ativa encontrada"]

    pct_ht = ativas[ativas["segmento"] == "High Ticket"].shape[0] / len(ativas) * 100

    if pct_ht < PCT_HIGH_TICKET_MIN:
        avisos.append(
            f"⚠️  High Ticket: {pct_ht:.1f}% das ativas — abaixo do esperado "
            f"({PCT_HIGH_TICKET_MIN}–{PCT_HIGH_TICKET_MAX}%) para a região"
        )
    elif pct_ht > PCT_HIGH_TICKET_MAX:
        avisos.append(
            f"⚠️  High Ticket: {pct_ht:.1f}% das ativas — acima do esperado "
            f"({PCT_HIGH_TICKET_MIN}–{PCT_HIGH_TICKET_MAX}%)"
        )
    else:
        pass  # dentro do intervalo esperado para a Baixada Santista

    return avisos


def validar_scoring(df_leads: pd.DataFrame) -> list[str]:
    avisos = []
    if "score" not in df_leads.columns:
        return ["❌ Coluna 'score' não encontrada"]
    if df_leads["score"].min() < 61:
        avisos.append("⚠️  Há leads com score < 61 — verifique o corte")
    if df_leads["score"].max() > 100:
        avisos.append("⚠️  Há scores > 100 — verifique os pesos em config.py")
    cnpjs_dup = df_leads["cnpj_basico"].duplicated().sum() if "cnpj_basico" in df_leads.columns else 0
    if cnpjs_dup > 0:
        avisos.append(f"⚠️  {cnpjs_dup:,} CNPJs duplicados em leads_qualificados.csv")
    return avisos


def validar_dashboard_db() -> list[str]:
    """Verifica se o dashboard.db foi gerado para o Metabase."""
    avisos = []
    db_path = os.path.join(DASHBOARDS_DIR, "dashboard.db")
    if not os.path.exists(db_path):
        avisos.append("⚠️  dashboard.db não encontrado — re-execute scoring.py")
    else:
        size_mb = os.path.getsize(db_path) / 1_048_576
        print(f"  ✔  dashboard.db (Metabase)             {size_mb:.1f} MB")
    return avisos


def main():
    print(f"\n{SEP}")
    print("  🔍 Validador de Pipeline — Fintech Baixada Santista".center(LARGURA))
    print(SEP)

    print("\n  Arquivos gerados pelo pipeline:")
    arquivos = {
        "empresas_raw.csv":         os.path.join(DATA_RAW,       "empresas_raw.csv"),
        "empresas_segmentadas.csv": os.path.join(DATA_PROCESSED, "empresas_segmentadas.csv"),
        "setor_relevante.csv":      os.path.join(DATA_PROCESSED, "setor_relevante.csv"),
        "leads_qualificados.csv":   os.path.join(DASHBOARDS_DIR, "leads_qualificados.csv"),
        "tam_por_municipio.csv":    os.path.join(DASHBOARDS_DIR, "tam_por_municipio.csv"),
        "setores_ranking.csv":      os.path.join(DASHBOARDS_DIR, "setores_ranking.csv"),
    }
    todos_ok = all(checar_arquivo(path, nome) for nome, path in arquivos.items())
    avisos_db = validar_dashboard_db()

    if not todos_ok:
        print(f"\n  ❌ Pipeline incompleto — execute os scripts na ordem:")
        print(f"     python extrator_cnpj.py")
        print(f"     python extrator_caged.py")
        print(f"     python etl.py")
        print(f"     python scoring.py")
        return

    df_seg   = pd.read_csv(arquivos["empresas_segmentadas.csv"], low_memory=False)
    df_leads = pd.read_csv(arquivos["leads_qualificados.csv"],   low_memory=False)

    todos_avisos = []
    todos_avisos += validar_volumes(df_seg)
    todos_avisos += validar_segmentacao(df_seg)
    todos_avisos += validar_scoring(df_leads)
    todos_avisos += avisos_db

    print(f"\n{SEP_FIN}")
    print(f"  📊 Volumes por município vs benchmarks SEBRAE")
    print(f"{SEP_FIN}")
    contagem = df_seg.groupby("municipio_nome").size()
    for municipio, ref in BENCHMARKS_EMPRESAS.items():
        total  = contagem.get(municipio, 0)
        status = "✔" if ref["min"] <= total <= ref["max"] else "⚠️ "
        esperado = f"{ref['min']:,}–{ref['max']:,}"
        print(f"  {status} {municipio:<16} {total:>8,}   esperado: {esperado}")
    print(f"{SEP_FIN}")

    # Resumo de segmentação
    ativas = df_seg[df_seg["segmento"] != "Inativa"]
    pct_ht = ativas[ativas["segmento"] == "High Ticket"].shape[0] / len(ativas) * 100
    print(f"\n  High Ticket: {pct_ht:.1f}% das empresas ativas")
    print(f"  Intervalo esperado para a Baixada Santista: {PCT_HIGH_TICKET_MIN}–{PCT_HIGH_TICKET_MAX}%")

    print(f"\n{SEP}")
    if not todos_avisos:
        print(f"  ✅ Pipeline validado — todos os dados dentro do esperado")
    else:
        print(f"  ⚠️  {len(todos_avisos)} aviso(s):\n")
        for aviso in todos_avisos:
            print(f"  {aviso}")
    print(SEP)
    print()


if __name__ == "__main__":
    main()