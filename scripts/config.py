"""
config.py — v4 CORRIGIDO

Corrigido com base em análise real das naturezas jurídicas do banco CNPJ.
Naturezas que realmente existem e são relevantes para fintech.
"""

import os
import pandas as pd

# ─────────────────────────────────────────────────────────────
# CAMINHOS
# ─────────────────────────────────────────────────────────────
BASE_DIR       = os.path.dirname(os.path.abspath(__file__))
DATA_DIR       = os.path.join(BASE_DIR, "..", "data")
DATA_RAW       = os.path.join(DATA_DIR, "raw")
DATA_PROCESSED = os.path.join(DATA_DIR, "processed")
DASHBOARDS_DIR = os.path.join(BASE_DIR, "..", "dashboards")
MUNICIPIOS_DIM = os.path.join(DATA_DIR, "municipios_dim.csv")

# Path para banco SQLite (gerado pelo cnpj-sqlite)
CNPJ_DB_PATH   = r"C:\Users\guilh\Downloads\cnpj-sqlite\dados-publicos\cnpj.db"

# ─────────────────────────────────────────────────────────────
# DIMENSÃO DE MUNICÍPIOS — lida do CSV externo
# ─────────────────────────────────────────────────────────────
def carregar_municipios() -> pd.DataFrame:
    """
    Lê data/municipios_dim.csv e retorna DataFrame com todos os municípios alvo.
    Colunas: municipio_nome, ibge, rf, uf, cep_inicio, cep_fim
    """
    if not os.path.exists(MUNICIPIOS_DIM):
        raise FileNotFoundError(
            f"Arquivo de dimensão não encontrado: {MUNICIPIOS_DIM}\n"
            f"Crie o arquivo data/municipios_dim.csv antes de executar."
        )
    df = pd.read_csv(MUNICIPIOS_DIM, dtype=str)
    return df

# Carrega uma vez e expõe como dicionários para uso nos scripts
_dim = carregar_municipios()

# {nome: codigo_rf_str}    — usado pelo extrator_cnpj.py (filtro WHERE)
MUNICIPIOS_RF = dict(zip(_dim["municipio_nome"], _dim["rf"]))

# set de códigos RF         — usado no filtro de chunks
CODIGOS_RF_ALVO = set(_dim["rf"].tolist())

# ─────────────────────────────────────────────────────────────
# NATUREZAS JURÍDICAS — CORRIGIDAS COM BASE EM DADOS REAIS
#
# Referência: análise de natureza_juridica no banco CNPJ.
# Estes códigos realmente existem nos dados de 2026.
# ─────────────────────────────────────────────────────────────

# Low Ticket: EI, MEI, Simples Pura (pequenos)
NATUREZA_LOW_TICKET = {
    "2135",  # Empresário Individual (EI) — 225k registros
    "2305",  # MEI (se existir) — raramente em SQLite completo
    "2232",  # Sociedade Simples Pura — 469 registros
}

# High Ticket: Ltda grande, SA Fechada (estruturadas, capital alto)
NATUREZA_HIGH_TICKET = {
    "2062",  # Sociedade Empresária Limitada (Ltda) — 59.5k registros ✅
    "2054",  # Sociedade Anônima Fechada (SA) — 196 registros ✅
}

# Naturezas a EXCLUIR — não são clientes de fintech
NATUREZAS_EXCLUIR = {
    "3085",  # Condomínio Edilício
    "3069",  # Fundação Privada
    "3999",  # Associação Privada
    "1244",  # Órgão Público Federal
    "1333",  # Órgão Público Municipal
    "1031",  # Órgão Público Estadual
    "1120",  # Órgão Público Federal
    "1031",  # Câmara Municipal
    "4014",  # Serviço Social Autônomo
}

# Proxy de High Ticket via capital social (R$)
CAPITAL_SOCIAL_HIGH_TICKET = 500_000
PORTE_HIGH_TICKET          = {"5", "05"}

# ─────────────────────────────────────────────────────────────
# SETORES DE INTERESSE (seção CNAE — letra)
# ─────────────────────────────────────────────────────────────
CNAES_INTERESSE = {
    "H": "Transporte e Armazenagem",              # Porto de Santos
    "G": "Comércio",
    "I": "Alojamento e Alimentação",
    "J": "Informação e Comunicação",
    "K": "Atividades Financeiras",
    "M": "Atividades Profissionais e Técnicas",
    "F": "Construção",
    "C": "Indústria de Transformação",
    "N": "Serviços Administrativos",
    "Q": "Saúde e Serviços Sociais",
}

# ─────────────────────────────────────────────────────────────
# SCORING — PESOS (somam 100)
# ─────────────────────────────────────────────────────────────
PESOS_SCORE = {
    "empresa_ativa":      30,
    "tempo_operacao_anos": 20,
    "setor_relevante":    25,
    "multiplos_socios":   15,
    "high_ticket_proxy":  10,
}