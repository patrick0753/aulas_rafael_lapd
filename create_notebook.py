import json

nb = {
    'nbformat': 4,
    'nbformat_minor': 5,
    'metadata': {
        'kernelspec': {
            'display_name': 'Python 3',
            'language': 'python',
            'name': 'python3'
        },
        'language_info': {
            'name': 'python',
            'version': '3.11.0'
        }
    },
    'cells': []
}

def md(source):
    lines = [line + '\n' for line in source.split('\n')]
    if lines:
        lines[-1] = lines[-1].rstrip('\n')  # last line no trailing newline
    nb['cells'].append({'cell_type': 'markdown', 'metadata': {}, 'source': lines})

def code(source):
    lines = [line + '\n' for line in source.split('\n')]
    if lines:
        lines[-1] = lines[-1].rstrip('\n')
    nb['cells'].append({'cell_type': 'code', 'metadata': {}, 'source': lines, 'execution_count': None, 'outputs': []})

# ====== CELULAS ======

md("""# 🧓 Rede Saber 60+ — Consumo da API SIDRA/IBGE (Censo 2022)
## UF: Mato Grosso (MT)

**Objetivo:** Consumir a API pública do IBGE (SIDRA) para obter dados de população idosa (65+) por município do Mato Grosso, organizando os resultados em DataFrames.

**Fonte:** IBGE — Censo Demográfico 2022 — Tabela 9514
*(População residente, por sexo, idade e forma de declaração da idade)*

**API:** https://apisidra.ibge.gov.br

> A lógica de consumo por blocos (paginação) segue o padrão aprendido na aula de Compras Governamentais.""")

md("## 1. Bibliotecas")

code("""import requests
import pandas as pd
import matplotlib.pyplot as plt
import time
import json""")

md("""## 2. Configuração da API SIDRA

A API SIDRA utiliza URLs com parâmetros no caminho (path parameters), diferente da API de Compras que usa query parameters.

**Estrutura:**
```
https://apisidra.ibge.gov.br/values/t/{tabela}/n{nivel}/{territorial}/v/{variavel}/p/{periodo}/c{classificacao}/{categorias}
```

**Parâmetros que usaremos:**
- `t/9514` — Tabela 9514 (População residente por sexo e idade)
- `n6/in n3 51` — Nível municipal (`n6`), filtrado pelo estado MT (código `51`)
- `v/93` — Variável: População residente
- `p/2022` — Período: Censo 2022
- `c2/6794` — Sexo: Total
- `c287/{codigos}` — Faixas etárias
- `f/n` — Formato numérico""")

code("""BASE_URL = "https://apisidra.ibge.gov.br/values"

# Tabela do Censo 2022 - Populacao residente por sexo e idade
TABELA = "9514"

# UF: Mato Grosso = codigo IBGE 51
UF_CODIGO = "51"

# Codigos das faixas etarias 65+ na classificacao c287
FAIXAS_65_MAIS = {
    "93096": "65 a 69 anos",
    "93097": "70 a 74 anos",
    "93098": "75 a 79 anos",
    "49108": "80 a 84 anos",
    "49109": "85 a 89 anos",
    "60040": "90 a 94 anos",
    "60041": "95 a 99 anos",
    "6653":  "100 anos ou mais"
}

# Codigo para populacao total (todas as idades)
CODIGO_TOTAL = "100362"

print("Faixas etarias 65+:")
for cod, nome in FAIXAS_65_MAIS.items():
    print(f"  {cod}: {nome}")""")

md("""## 3. Função de consumo da API por blocos

Assim como na aula de Compras Governamentais, vamos consumir a API em **blocos** (chunks).

A API SIDRA não usa paginação clássica (`pagina=1, 2, 3...`), mas podemos dividir a consulta em blocos de faixas etárias para:
1. Evitar timeout em requisições muito grandes
2. Controlar o que está sendo baixado
3. Ter resiliência (se um bloco falhar, os outros já estão salvos)""")

code("""def consultar_sidra_bloco(tabela, uf_codigo, codigos_idade, variavel="93", periodo="2022"):
    \"\"\"
    Consulta a API SIDRA por um bloco de codigos de faixa etaria.
    
    Parametros
    ----------
    tabela : str
        Numero da tabela SIDRA
    uf_codigo : str
        Codigo IBGE da UF
    codigos_idade : list
        Lista de codigos c287 para as faixas etarias
    variavel : str
        Codigo da variavel (93 = populacao residente)
    periodo : str
        Ano de referencia
    
    Retorna
    -------
    list
        Registros JSON da resposta (sem o header)
    \"\"\"
    
    # Monta a string de codigos separados por virgula
    ids_idade = ",".join(codigos_idade)
    
    # Monta a URL completa
    url = (
        f"{BASE_URL}"
        f"/t/{tabela}"
        f"/n6/in%20n3%20{uf_codigo}"
        f"/v/{variavel}"
        f"/p/{periodo}"
        f"/c2/6794"           # Sexo = Total
        f"/c287/{ids_idade}"
        f"/f/n"               # Formato numerico
    )
    
    print(f"  Consultando: {ids_idade}")
    print(f"  URL: {url}")
    
    resposta = requests.get(url, timeout=120)
    resposta.raise_for_status()
    
    dados = resposta.json()
    
    # O primeiro registro eh o header (nomes das colunas)
    # Retornamos apenas os dados (a partir do indice 1)
    registros = dados[1:] if len(dados) > 1 else []
    
    print(f"  -> {len(registros)} registros obtidos")
    
    return registros


# Teste rapido com um bloco
teste = consultar_sidra_bloco(TABELA, UF_CODIGO, ["93096"])
print("\\nExemplo de registro:")
print(json.dumps(teste[0], ensure_ascii=False, indent=2))""")

md("""## 4. Coleta completa por blocos (idosos 65+)

Agora vamos iterar por **cada faixa etária como um bloco separado**, coletar os dados e acumular tudo em uma lista única — exatamente como a função `coletar_paginas()` da aula.""")

code("""def coletar_por_blocos(tabela, uf_codigo, faixas_etarias, pausa=2):
    \"\"\"
    Coleta dados da API SIDRA em blocos (um por faixa etaria).
    Equivalente a coletar_paginas da aula de Compras Governamentais.
    
    Parametros
    ----------
    tabela : str
        Numero da tabela
    uf_codigo : str
        Codigo da UF
    faixas_etarias : dict
        Dicionario {codigo: nome} das faixas
    pausa : int
        Segundos entre requisicoes (respeitar a API)
    
    Retorna
    -------
    pd.DataFrame
        DataFrame com todos os registros
    \"\"\"
    todos_registros = []
    
    codigos = list(faixas_etarias.keys())
    total_blocos = len(codigos)
    
    print(f"Iniciando coleta de {total_blocos} blocos...")
    print("=" * 60)
    
    for i, codigo in enumerate(codigos, 1):
        nome_faixa = faixas_etarias[codigo]
        print(f"\\nBloco {i}/{total_blocos}: {nome_faixa}")
        
        try:
            registros = consultar_sidra_bloco(tabela, uf_codigo, [codigo])
            todos_registros.extend(registros)
            print(f"  Acumulado: {len(todos_registros)} registros")
        except Exception as e:
            print(f"  ERRO no bloco {i}: {e}")
        
        # Pausa entre requisicoes para nao sobrecarregar a API
        if i < total_blocos:
            print(f"  Aguardando {pausa}s...")
            time.sleep(pausa)
    
    print("\\n" + "=" * 60)
    print(f"Coleta finalizada! Total: {len(todos_registros)} registros")
    
    # Converte para DataFrame
    df = pd.DataFrame(todos_registros)
    
    return df


# Executar a coleta completa
df_idosos = coletar_por_blocos(TABELA, UF_CODIGO, FAIXAS_65_MAIS, pausa=2)

print("\\nDimensao:", df_idosos.shape)
df_idosos.head()""")

md("""## 5. Coletar população total por município (bloco único)

Para calcular indicadores como o **percentual de idosos**, precisamos também da população total.""")

code("""print("Coletando populacao total por municipio...")
registros_total = consultar_sidra_bloco(
    TABELA, UF_CODIGO, [CODIGO_TOTAL]
)

df_pop_total = pd.DataFrame(registros_total)
print("\\nDimensao:", df_pop_total.shape)
df_pop_total.head()""")

md("""## 6. Limpeza e transformação dos dados

### 6.1 Renomear colunas
A API SIDRA retorna colunas com nomes codificados. Vamos renomear para facilitar a análise.""")

code("""# Mapeamento de colunas
COLUNAS_RENOMEAR = {
    "V": "valor",
    "D1N": "municipio",
    "D2N": "variavel",
    "D3N": "ano",
    "D4N": "sexo",
    "D5N": "faixa_etaria",
    "D6N": "forma_declaracao",
    "NN": "nivel_territorial",
    "MN": "unidade_medida"
}

# Aplicar renomeacao
df_idosos = df_idosos.rename(columns=COLUNAS_RENOMEAR)
df_pop_total = df_pop_total.rename(columns=COLUNAS_RENOMEAR)

print("Colunas df_idosos:", list(df_idosos.columns))
print("Colunas df_pop_total:", list(df_pop_total.columns))""")

code("""# Converter valor para numerico
df_idosos["valor"] = pd.to_numeric(df_idosos["valor"], errors="coerce")
df_pop_total["valor"] = pd.to_numeric(df_pop_total["valor"], errors="coerce")

# Extrair apenas o nome do municipio (sem " - MT")
df_idosos["municipio_nome"] = df_idosos["municipio"].str.replace(" - MT", "", regex=False)
df_pop_total["municipio_nome"] = df_pop_total["municipio"].str.replace(" - MT", "", regex=False)

print("Tipos de dados:")
print(df_idosos.dtypes)""")

md("### 6.2 Verificar dados ausentes e duplicidades")

code("""print("=== Idosos 65+ ===")
print("Linhas duplicadas:", df_idosos.duplicated().sum())
print("\\nValores ausentes (%):")
print(df_idosos.isna().mean().mul(100).round(2))

print("\\n=== Populacao Total ===")
print("Linhas duplicadas:", df_pop_total.duplicated().sum())
print("\\nValores ausentes (%):")
print(df_pop_total.isna().mean().mul(100).round(2))""")

md("""## 7. Análise: Total de idosos 65+ por município

Vamos agrupar os dados por município, somando todas as faixas etárias 65+.""")

code("""# Somar todas as faixas 65+ por municipio
df_idosos_municipio = (
    df_idosos
    .groupby("municipio_nome")["valor"]
    .sum()
    .reset_index()
    .rename(columns={"valor": "pop_65_mais"})
)

# Juntar com populacao total
df_pop = df_pop_total[["municipio_nome", "valor"]].rename(
    columns={"valor": "pop_total"}
)

df_completo = df_idosos_municipio.merge(df_pop, on="municipio_nome", how="left")

# Calcular percentual de idosos
df_completo["pct_idosos"] = (
    df_completo["pop_65_mais"] / df_completo["pop_total"] * 100
).round(2)

# Ordenar por percentual
df_completo = df_completo.sort_values("pct_idosos", ascending=False).reset_index(drop=True)

print(f"Municipios analisados: {len(df_completo)}")
print(f"Populacao total MT: {df_completo['pop_total'].sum():,.0f}")
print(f"Idosos 65+ MT: {df_completo['pop_65_mais'].sum():,.0f}")
print(f"Percentual medio de idosos: {df_completo['pct_idosos'].mean():.2f}%")

df_completo.head(15)""")

md("## 8. Estatística descritiva")

code("""df_completo[["pop_total", "pop_65_mais", "pct_idosos"]].describe().T""")

md("""## 9. Visualizações

### 9.1 Top 20 municípios com maior percentual de idosos""")

code("""top20 = df_completo.nlargest(20, "pct_idosos").sort_values("pct_idosos")

plt.figure(figsize=(12, 8))
plt.barh(top20["municipio_nome"], top20["pct_idosos"], color="#2196F3")
plt.xlabel("Percentual de idosos 65+ (%)")
plt.ylabel("Município")
plt.title("Top 20 Municípios de MT com maior percentual de idosos (65+)\\nCenso 2022 - IBGE")
plt.tight_layout()
plt.show()""")

md("### 9.2 Distribuição dos idosos por faixa etária em todo o MT")

code("""# Agrupar por faixa etaria
df_faixas = (
    df_idosos
    .groupby("faixa_etaria")["valor"]
    .sum()
    .reset_index()
    .sort_values("valor", ascending=False)
)

plt.figure(figsize=(10, 6))
plt.bar(df_faixas["faixa_etaria"], df_faixas["valor"], color="#FF9800")
plt.xlabel("Faixa Etária")
plt.ylabel("População")
plt.title("Distribuição da População Idosa (65+) por Faixa Etária\\nMato Grosso - Censo 2022")
plt.xticks(rotation=45, ha="right")
plt.tight_layout()
plt.show()

print("\\nResumo por faixa etaria:")
print(df_faixas.to_string(index=False))""")

md("### 9.3 Top 20 municípios com maior número absoluto de idosos")

code("""top20_abs = df_completo.nlargest(20, "pop_65_mais").sort_values("pop_65_mais")

plt.figure(figsize=(12, 8))
plt.barh(top20_abs["municipio_nome"], top20_abs["pop_65_mais"], color="#4CAF50")
plt.xlabel("Número de idosos 65+")
plt.ylabel("Município")
plt.title("Top 20 Municípios de MT com mais idosos (65+) em números absolutos\\nCenso 2022 - IBGE")
plt.tight_layout()
plt.show()""")

md("### 9.4 Boxplot do percentual de idosos por município")

code("""plt.figure(figsize=(8, 5))
plt.boxplot(df_completo["pct_idosos"].dropna(), vert=False, patch_artist=True,
            boxprops=dict(facecolor="#E3F2FD"))
plt.xlabel("Percentual de idosos 65+ (%)")
plt.title("Distribuição do Percentual de Idosos por Município\\nMato Grosso - Censo 2022")
plt.tight_layout()
plt.show()

print("Municipios com maior envelhecimento (acima do P75):")
p75 = df_completo["pct_idosos"].quantile(0.75)
print(f"Percentil 75: {p75:.2f}%")
print(df_completo[df_completo["pct_idosos"] >= p75][["municipio_nome", "pct_idosos", "pop_65_mais", "pop_total"]].to_string(index=False))""")

md("""## 10. Exportar dados para uso posterior

Os DataFrames gerados podem ser salvos em CSV para uso em outras etapas do projeto (modelo de dados, dashboard, etc.).""")

code("""# Salvar CSVs
df_completo.to_csv("idosos_65mais_municipios_MT_censo2022.csv", index=False, encoding="utf-8-sig")
df_idosos.to_csv("idosos_65mais_faixas_MT_censo2022.csv", index=False, encoding="utf-8-sig")

print("Arquivos salvos:")
print("  - idosos_65mais_municipios_MT_censo2022.csv")
print("  - idosos_65mais_faixas_MT_censo2022.csv")
print("\\nPronto para uso no Observatorio e no modelo de dados!")""")

md("""## 11. Resumo da Fonte de Dados

| Campo | Valor |
|-------|-------|
| **Fonte** | IBGE — Censo Demográfico 2022 |
| **API** | SIDRA (`apisidra.ibge.gov.br`) |
| **Tabela** | 9514 |
| **Variável** | 93 (População residente) |
| **Classificação** | c287 (Idade) |
| **Nível territorial** | Municípios (n6) |
| **UF** | Mato Grosso (51) |
| **Período** | 2022 |
| **Acesso** | Aberto (sem autenticação) |
| **Formato** | JSON |
| **Frequência** | Decenal (Censo) |""")

# Salvar notebook
output_path = r'c:\Users\52068085801\Downloads\Rede_Saber60_API_SIDRA_MT.ipynb'
with open(output_path, 'w', encoding='utf-8') as f:
    json.dump(nb, f, ensure_ascii=False, indent=1)

print(f'Notebook salvo em: {output_path}')
print(f'Total de celulas: {len(nb["cells"])}')
