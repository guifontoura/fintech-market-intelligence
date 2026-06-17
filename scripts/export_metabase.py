import os
import sqlite3
import pandas as pd

# Caminhos
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DASHBOARDS_DIR = os.path.join(BASE_DIR, "..", "dashboards")

# Criar (ou conectar) a um banco leve exclusivo para os gráficos
conn = sqlite3.connect(os.path.join(DASHBOARDS_DIR, "metabase_insights.db"))

# Ler as duas visões agregadas e salvar no banco
df_tam = pd.read_csv(os.path.join(DASHBOARDS_DIR, "tam_por_municipio.csv"))
df_ranking = pd.read_csv(os.path.join(DASHBOARDS_DIR, "setores_ranking.csv"))

df_tam.to_sql("tam_por_municipio", conn, if_exists="replace", index=False)
df_ranking.to_sql("setores_ranking", conn, if_exists="replace", index=False)

print("🎯 Banco 'metabase_insights.db' gerado com sucesso para o Metabase!")
conn.close()