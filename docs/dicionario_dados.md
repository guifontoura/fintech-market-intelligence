# Dicionário de Dados

## empresas_segmentadas.csv

| Campo            | Tipo    | Descrição                                              |
|------------------|---------|--------------------------------------------------------|
| cnpj             | string  | CNPJ da empresa (14 dígitos)                           |
| razao_social     | string  | Razão social registrada na Receita Federal             |
| municipio_nome   | string  | Nome do município (Baixada Santista)                   |
| municipio_ibge   | int     | Código IBGE do município                               |
| natureza_juridica| string  | Código de natureza jurídica (RF)                       |
| cnae_fiscal      | string  | CNAE principal da empresa                              |
| situacao         | string  | Situação cadastral (Ativa, Baixada, Suspensa…)         |
| capital_social   | float   | Capital social declarado em R$                         |
| anos_operacao    | float   | Anos desde a data de abertura até hoje                 |
| segmento         | string  | "High Ticket" ou "Low Ticket" (calculado)              |
| score            | int     | Score de propensão 0–100 (calculado)                   |
| score_label      | string  | "Frio" / "Morno" / "Quente" / "Hot Lead"               |

---

## setores_crescimento.csv (CAGED)

| Campo            | Tipo    | Descrição                                              |
|------------------|---------|--------------------------------------------------------|
| municipio_nome   | string  | Nome do município                                      |
| secao_cnae       | string  | Letra da seção CNAE (A–S)                              |
| setor_nome       | string  | Nome legível do setor                                  |
| admissoes        | int     | Total de admissões no período                          |
| demissoes        | int     | Total de demissões no período                          |
| saldo            | int     | Saldo líquido (admissões − demissões)                  |
| em_crescimento   | bool    | True se saldo > 0                                      |

---

## leads_qualificados.csv (dashboard)

Subconjunto de empresas_segmentadas com score ≥ 60.
Pronto para importar no Metabase como lista de prospecção.

---

## tam_por_municipio.csv (dashboard)

| Campo               | Tipo  | Descrição                                           |
|---------------------|-------|-----------------------------------------------------|
| municipio_nome      | str   | Nome do município                                   |
| segmento            | str   | High Ticket ou Low Ticket                           |
| quantidade          | int   | Total de empresas no segmento                       |
| score_medio         | float | Score médio das empresas                            |
| hot_leads           | int   | Empresas com score_label = "Hot Lead"               |
| ltv_estimado_total  | float | LTV total do segmento (quantidade × LTV médio)      |
| ltv_hot_leads       | float | LTV dos Hot Leads (hot_leads × LTV médio)           |

> ⚠️ LTV médio é um valor placeholder. Substitua com os dados reais
> fornecidos pelo Giovani (ticket médio × tempo médio de contrato).
