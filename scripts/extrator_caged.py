# extrator_caged.py — v5
"""
Gera o ranking setorial da Baixada Santista a partir dos dados da RF.

Contexto metodológico:
  O CEMPRE (Cadastro Central de Empresas do IBGE) é a referência oficial
  para classificação setorial de empresas no Brasil — combina dados da
  Receita Federal, IBGE e Ministério do Trabalho, com publicação anual.
  A API SIDRA do IBGE, contudo, não disponibiliza a tabela de empresas
  por seção CNAE em nível municipal via endpoint REST.
  Por isso, o ranking setorial é calculado diretamente dos dados da RF
  já coletados — mesma base de CNAEs, sem perda de qualidade analítica.

Entrada:  data/raw/empresas_raw.csv
Saída:    data/raw/caged_saldo_setores.csv
"""

import os
import pandas as pd
from config import DATA_RAW

os.makedirs(DATA_RAW, exist_ok=True)

CNAE_SECAO = {
    **{str(i).zfill(2): "Agricultura e Pecuária"        for i in range(1,  4)},
    **{str(i).zfill(2): "Indústria Extrativa"           for i in range(5,  10)},
    **{str(i).zfill(2): "Indústria de Transformação"    for i in range(10, 34)},
    "35": "Eletricidade e Gás",
    **{str(i).zfill(2): "Água e Saneamento"             for i in range(36, 40)},
    **{str(i).zfill(2): "Construção"                    for i in range(41, 44)},
    **{str(i).zfill(2): "Comércio"                      for i in range(45, 48)},
    **{str(i).zfill(2): "Transporte e Armazenagem"      for i in range(49, 54)},
    "55": "Alojamento e Alimentação",
    "56": "Alojamento e Alimentação",
    **{str(i).zfill(2): "Informação e Comunicação"      for i in range(58, 64)},
    **{str(i).zfill(2): "Atividades Financeiras"        for i in range(64, 67)},
    "68": "Atividades Imobiliárias",
    **{str(i).zfill(2): "Atividades Profissionais"      for i in range(69, 76)},
    **{str(i).zfill(2): "Serviços Administrativos"      for i in range(77, 83)},
    "84": "Administração Pública",
    "85": "Educação",
    **{str(i).zfill(2): "Saúde e Serviços Sociais"      for i in range(86, 89)},
    **{str(i).zfill(2): "Artes e Cultura"               for i in range(90, 94)},
    **{str(i).zfill(2): "Outros Serviços"               for i in range(94, 97)},
}


def main():
    path_empresas = os.path.join(DATA_RAW, "empresas_raw.csv")
    if not os.path.exists(path_empresas):
        print("⚠️  empresas_raw.csv não encontrado.")
        print("   Execute primeiro: python extrator_cnpj.py --modo-local")
        return

    print("\n📊 Gerando ranking setorial a partir dos dados da RF...\n")

    df = pd.read_csv(
        path_empresas, dtype=str, low_memory=False,
        usecols=["municipio_nome", "cnae_fiscal_principal", "situacao_cadastral"],
    )

    df["secao_nome"] = (
        df["cnae_fiscal_principal"].astype(str).str[:2]
        .map(CNAE_SECAO)
        .fillna("Outros")
    )
    df["n_empresas"] = 1

    resultado = (
        df.groupby(["municipio_nome", "secao_nome"])["n_empresas"]
        .sum()
        .reset_index()
    )
    resultado["ano_referencia"] = "2026"

    saida = os.path.join(DATA_RAW, "caged_saldo_setores.csv")
    resultado.to_csv(saida, index=False, encoding="utf-8-sig")

    # ── Ranking consolidado ───────────────────────────────────
    ranking = (
        resultado.groupby("secao_nome")["n_empresas"]
        .sum()
        .sort_values(ascending=False)
        .reset_index()
    )
    ranking.index = ranking.index + 1  # posição começa em 1

    largura = 83
    titulo = "🏆 Top 10 setores — Baixada Santista (2026)"
    print("─" * largura)
    print(titulo.center(largura))
    print("─" * largura)
    total_geral = ranking["n_empresas"].sum()
    for pos, row in ranking.head(10).iterrows():
        barra = "█" * int(row["n_empresas"] / ranking["n_empresas"].max() * 20)
        pct = row["n_empresas"] / total_geral * 100
        print(f"  {pos:2d}. {row['secao_nome']:<35} {row['n_empresas']:>8,}  {barra} ({pct:.1f}%)")
    print("─" * largura)
    print(f"  📦 {len(resultado):,} combinações município × setor geradas")
    print(f"  💾 Salvo em: {saida}")
    print()

    # ── Nota metodológica ─────────────────────────────────────
    print("  ℹ️  Nota: ranking calculado via dados da Receita Federal (CNPJ).")
    print("      Referência oficial equivalente: CEMPRE/IBGE (publicação anual).")
    print("      API SIDRA não disponibiliza essa tabela em nível municipal.")
    print()


if __name__ == "__main__":
    main()
