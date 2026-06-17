# atualizar.py
"""
Roda o pipeline completo do Fintech Market Intelligence em sequência.

PRÉ-REQUISITO (fazer antes de rodar este script):
  1. Baixe os ZIPs atualizados da RF:
     https://dados-abertos-rf-cnpj.casadosdados.com.br/arquivos/
  2. Substitua os ZIPs antigos em:
     Downloads/cnpj-sqlite/dados-publicos-zip/
  3. Rode o cnpj-sqlite para regenerar o banco:
     cd Downloads/cnpj-sqlite
     python dados_cnpj_para_sqlite.py

Depois disso, rode este script:
  cd scripts
  python atualizar.py

Tempo estimado: 3-5 minutos
"""

import subprocess
import sys
import time
import os

SCRIPTS = [
    ("extrator_cnpj.py",   "Extração do SQLite → empresas_raw.csv"),
    ("extrator_caged.py",  "Ranking setorial → caged_saldo_setores.csv"),
    ("etl.py",             "Limpeza e segmentação → empresas_segmentadas.csv"),
    ("scoring.py",         "Score e TAM → dashboards/ + dashboard.db"),
    ("validador.py",       "Validação contra benchmarks SEBRAE"),
]

LARGURA = 62
SEP     = "━" * LARGURA

def rodar(script, descricao):
    print(f"\n  ▶  {descricao}")
    inicio = time.time()
    resultado = subprocess.run(
        [sys.executable, script],
        capture_output=False,
        text=True,
    )
    tempo = time.time() - inicio
    if resultado.returncode != 0:
        print(f"\n  ❌ Erro em {script} — pipeline interrompido.")
        print(f"     Verifique o output acima e corrija antes de continuar.")
        sys.exit(1)
    print(f"  ✔  Concluído em {tempo:.1f}s")
    return tempo

def main():
    print(f"\n{SEP}")
    print("  🔄  Fintech Market Intelligence — Atualização".center(LARGURA))
    print(SEP)
    print(f"\n  {len(SCRIPTS)} scripts na fila. Tempo estimado: 3-5 minutos.\n")

    # Garante que está rodando da pasta scripts/
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)

    inicio_total = time.time()
    tempos = []

    for i, (script, descricao) in enumerate(SCRIPTS, 1):
        print(f"{SEP}")
        print(f"  [{i}/{len(SCRIPTS)}] {script}")
        t = rodar(script, descricao)
        tempos.append((script, t))

    total = time.time() - inicio_total

    print(f"\n{SEP}")
    print(f"  ✅ Pipeline completo em {total:.0f}s".center(LARGURA))
    print(SEP)
    print(f"\n  Resumo de tempo:")
    for script, t in tempos:
        print(f"    {script:<25} {t:.1f}s")
    print(f"    {'TOTAL':<25} {total:.1f}s")
    print(f"\n  📊 Dashboard atualizado: dashboards/dashboard.db")
    print(f"  🔄 Atualize o Metabase para ver os novos dados.\n")

if __name__ == "__main__":
    main()