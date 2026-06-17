# 📊 Fintech Market Intelligence — Baixada Santista

Pipeline de inteligência de mercado B2B para mapeamento do TAM regional,
segmentação de leads e scoring de propensão — processando 71M de registros da Receita Federal, 
identificando +22k Hot Leads com R$391M de LTV estimado para produto financeiro premium.

## Resultados
- **287.156 empresas** mapeadas em 9 municípios (validadas vs SEBRAE 2024)
- **166.726 leads qualificados** com score de propensão ≥ 61
- **22.200 Hot Leads** (score ≥ 81) — empresas com maior potencial
- **R$1,5B de TAM** estimado no mercado endereçável total
- **R$442M de LTV** concentrado nos Hot Leads High Ticket
- Validado contra benchmarks SEBRAE (9/9 municípios ✔)

---

⚡ **Escalabilidade e Performance:** Pipeline desenhado para processar a base
completa da Receita Federal do Brasil — **71 milhões de registros (41 GB)** —
com filtros indexados em SQLite (2 índices compostos criados: `idx_estab_mun_sit`
e `idx_socios_cnpj_basico`), extraindo, segmentando e pontuando os leads da
região alvo em ~115 segundos. Para expandir para SP inteiro ou Brasil: edite
apenas `data/municipios_dim.csv` — nenhum script precisa ser alterado.

---

## 🎯 Perguntas respondidas

- Qual o **TAM** (Total Addressable Market) High Ticket vs Low Ticket?
- Quais **setores** concentram mais empresas e maior LTV na região?
- Qual o **score de propensão** de cada empresa (0–100)?
- Quais são os **Hot Leads** com maior LTV estimado?
- Qual o **crescimento** de abertura de empresas por ano?
- Onde estão as empresas por **porte** (micro, pequeno, médio/grande)?

---

## 🏙️ Municípios analisados

Configurados em `data/municipios_dim.csv` — editável para expandir para
qualquer estado ou Brasil inteiro sem alterar código.

| Município    | IBGE    | RF   | Empresas | Hot Leads |
|--------------|---------|------|----------|-----------|
| Santos       | 3548500 | 7071 | ~85k     | ~10.8k    |
| São Vicente  | 3551702 | 7121 | ~49k     | ~1.9k     |
| Guarujá      | 3518701 | 6475 | ~45k     | ~2.3k     |
| Praia Grande | 3541000 | 6921 | ~61k     | ~3.3k     |
| Cubatão      | 3513801 | 6371 | ~13k     | ~795      |
| Bertioga     | 3506359 | 2965 | ~11k     | ~1.0k     |
| Itanhaém     | 3523909 | 6543 | ~15k     | ~762      |
| Mongaguá     | 3531100 | 6723 | ~10k     | ~485      |
| Peruíbe      | 3537008 | 6853 | ~11k     | ~798      |

---

## 🏗️ Arquitetura de Dados (Medallion)

```
BRONZE → SQLite (cnpj.db, 41 GB)   Brasil inteiro — fonte da verdade
SILVER → data/raw/                  Dados filtrados e extraídos por região
GOLD   → data/processed/            Dados limpos, segmentados, enriquecidos
PLATINUM → dashboards/              TAM, leads qualificados, ranking setorial
           dashboards/dashboard.db  Banco leve para Metabase
```

---

## 🔄 Fluxo de execução

### Pré-requisito — Big Data Local (SQLite, uma vez ~2h)

```bash
# 1. Baixe os 37 ZIPs da RF (~4 GB compactados):
#    https://dados-abertos-rf-cnpj.casadosdados.com.br/arquivos/
#    Inclui: Estabelecimentos0-9, Empresas0-9, Socios0-9,
#            Simples, Cnaes, Municipios, Naturezas, Paises, Qualificacoes, Motivos

# 2. Coloque em: Downloads/cnpj-sqlite/dados-publicos-zip/

# 3. Gere o banco SQLite (cnpj-sqlite do rictom):
cd Downloads/cnpj-sqlite
python dados_cnpj_para_sqlite.py
# Gera cnpj.db com Brasil inteiro (~41 GB após índices)

# 4. Crie os índices compostos (uma vez, ~10 min):
python -c "
import sqlite3
conn = sqlite3.connect(r'Downloads/cnpj-sqlite/dados-publicos/cnpj.db')
conn.execute('CREATE INDEX IF NOT EXISTS idx_estab_mun_sit ON estabelecimento(municipio, situacao_cadastral, uf, matriz_filial)')
conn.commit()
conn.execute('CREATE INDEX IF NOT EXISTS idx_socios_cnpj_basico ON socios(cnpj_basico)')
conn.commit()
conn.close()
print('Índices criados')
"
```

### Pipeline principal (a cada atualização mensal)

```bash
cd scripts

python extrator_cnpj.py    # lê 71M de linhas do SQLite → empresas_raw.csv    (~115s)
python extrator_caged.py   # ranking setorial → caged_saldo_setores.csv        (~5s)
python etl.py              # limpeza e segmentação → empresas_segmentadas.csv  (~15s)
python scoring.py          # score e TAM → dashboards/ + dashboard.db          (~60s)
python validador.py        # valida volumes contra benchmarks SEBRAE
```

---

## 📊 Critério de Segmentação High Ticket

Empresa é classificada como **High Ticket** se atender qualquer um dos critérios:

| Critério | Descrição |
|----------|-----------|
| **A** | Natureza Jurídica Ltda (2062) ou SA (2054) **E** Capital Social ≥ R$500.000 |
| **B** | Porte RF = 5 (Médio/Grande — faturamento acima de R$4,8M/ano) |

Critério B captura empresas que abrem com capital mínimo mas têm faturamento real declarado no Simples Nacional — situação comum em 80% das Ltdas brasileiras.

---

## 🧮 Critério de Scoring (0–100 pts)

| Critério | Peso | Fonte |
|----------|------|-------|
| Empresa ativa (situação 02) | 30 pts | RF — situacao_cadastral |
| Setor de interesse da fintech | 25 pts | RF — cnae_fiscal_principal |
| Tempo de operação ≥ 2 anos | 20 pts | RF — data_inicio_atividades |
| Múltiplos sócios (≥ 2) | 15 pts | RF — tabela socios |
| Segmento High Ticket | 10 pts | Critério A ou B acima |

**Classificação:**
- 🔴 Hot Lead: 81–100 pts
- 🟠 Quente: 61–80 pts
- 🟡 Morno: 31–60 pts
- ⚪ Frio: 0–30 pts

---

## 📦 Dependências

```bash
pip install -r requirements.txt
```

| Biblioteca  | Uso                                      |
|-------------|------------------------------------------|
| `pandas`    | manipulação e merge de dados             |
| `sqlite3`   | conexão com banco CNPJ (stdlib Python)   |
| `openpyxl`  | leitura de Excel (opcional)              |

---

## 📁 Estrutura

```
fintech-market-intelligence/
├── data/
│   ├── municipios_dim.csv              ← fonte da verdade geográfica
│   ├── raw/
│   │   ├── empresas_raw.csv            ← output do extrator (~60 MB)
│   │   └── caged_saldo_setores.csv     ← ranking setorial
│   └── processed/
│       ├── empresas_segmentadas.csv    ← dados limpos + score base
│       └── setor_relevante.csv         ← setores por município
├── dashboards/
│   ├── leads_qualificados.csv          ← leads com score ≥ 61
│   ├── tam_por_municipio.csv           ← TAM e LTV por município
│   ├── setores_ranking.csv             ← ranking setorial consolidado
│   ├── distribuicao_score.csv          ← todas as empresas com score
│   └── dashboard.db                    ← banco SQLite para Metabase
└── scripts/
    ├── config.py                       ← parâmetros centrais + caminho SQLite
    ├── extrator_cnpj.py                ← extração do SQLite (v16)
    ├── extrator_caged.py               ← ranking setorial via RF
    ├── etl.py                          ← limpeza, segmentação, enriquecimento
    ├── scoring.py                      ← score de propensão e TAM
    ├── validador.py                    ← validação vs SEBRAE
    └── export_metabase.py              ← exporta para dashboard.db
```

---

## 📌 Notas importantes

- **Banco SQLite:** gerado pelo [cnpj-sqlite](https://github.com/rictom/cnpj-sqlite)
  — 67M empresas, 71M estabelecimentos, 27M sócios (atualizado maio/2026).
- **Índices compostos:** `idx_estab_mun_sit` e `idx_socios_cnpj_basico` precisam
  ser criados uma vez no banco — reduzem tempo de query de 411s para ~115s.
- **Códigos RF ≠ IBGE:** sistemas independentes, ambos mapeados em
  `data/municipios_dim.csv`.
- **LTV médio** em `scoring.py` é placeholder — substitua pelos valores
  reais da fintech.
- **Expansão:** para analisar SP inteiro (~645 municípios) ou Brasil, adicione
  os municípios em `data/municipios_dim.csv` — nenhum script precisa ser alterado.
  Estimativa de tempo: SP inteiro ~35-50 min, Brasil inteiro → recomenda-se DuckDB.

---

## 🗄️ Dashboard Metabase

O `scoring.py` gera automaticamente `dashboards/dashboard.db` com 4 tabelas:

| Tabela | Conteúdo |
|--------|----------|
| `leads_qualificados` | Empresas com score ≥ 61, ordenadas por score |
| `tam_por_municipio` | TAM, LTV e Hot Leads por município e segmento |
| `setores_ranking` | Ranking setorial com contagem de empresas |
| `distribuicao_score` | Todas as empresas com score, label e faixa |

Para conectar no Metabase: `Add Database → SQLite → caminho para dashboard.db`

---

## 🔗 Fontes de dados

- [Espelho RF — Casa dos Dados](https://dados-abertos-rf-cnpj.casadosdados.com.br/arquivos/)
- [cnpj-sqlite — rictom](https://github.com/rictom/cnpj-sqlite)
- [Observatório SEBRAE Santos](https://observatorio.sebrae.com.br/profile/geo/santos)
- [Base dos Dados](https://basedosdados.org) — IBGE, CAGED, RAIS