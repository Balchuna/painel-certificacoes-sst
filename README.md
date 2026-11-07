# Painel de Certificações SST

Projeto em construção. **Já existem a fase 1, com os dados de entrada, a fase 2, com o SQL de referência e o gabarito, e a fase 3, com o pacote do Power BI: consultas, medidas, tema e o passo a passo para montar.** O painel montado, com o PDF e as imagens, vem na fase 4 e precisa bater com o gabarito.

A pergunta que o painel vai responder: numa obra com cerca de 150 funcionários, quem está irregular hoje, o que vence nos próximos 30, 60 e 90 dias, e qual função e qual treinamento concentram as pendências?

Para entender o projeto sem jargão, leia [docs/COMO-FUNCIONA.md](docs/COMO-FUNCIONA.md). As escolhas e o porquê estão em [docs/DECISOES.md](docs/DECISOES.md).

## Os dados são sintéticos

Nenhum dado aqui é real. Funcionários, matrículas, datas e pendências saem de um sorteio com semente fixa, e o script não lê nenhum arquivo externo. Qualquer concentração de pendências foi colocada de propósito no gerador, para o painel ter o que mostrar. Não é achado sobre uma obra de verdade.

As regras de obrigatoriedade são parâmetros do modelo, não interpretação jurídica das NRs.

## O que há em `data/entrada`

**`controle_largo.xlsx`** imita uma planilha real e bagunçada.

| Aba | Conteúdo |
|---|---|
| `Controle` | Uma linha por funcionário e uma coluna por treinamento, com a emissão mais recente de cada item |
| `Historico` | As emissões anteriores: matrícula, treinamento e data |
| `Leia-me` | Aviso de que os dados são fictícios, e o que há nas abas e nos defeitos |

**`parametros.xlsx`** traz as regras, sem bagunça: é por ela que o resto se liga.

| Aba | Conteúdo |
|---|---|
| `Regra_Funcao_Treinamento` | SIM, NÃO ou CONDICIONAL para cada função e treinamento |
| `Treinamentos` | Código, nome e validade em meses (0 = sem vencimento fixo) |
| `Alertas` | Data de referência e janelas de 30, 60 e 90 dias |
| `Leia-me` | Aviso de que os dados são fictícios, e como ler as regras |

## Os defeitos plantados na aba `Controle`

Eles existem para a limpeza ter o que arrumar. Ela é feita aqui em Python, como referência, e o Power Query do painel vai precisar chegar aos mesmos números.

- Datas gravadas como texto em parte das linhas.
- Espaços sobrando em nomes, funções, equipes e datas em texto.
- Um funcionário duplicado: as duas linhas ficam iguais depois da limpeza.
- Uma data que não existe no calendário: 31/02/2025.

## Como reproduzir

Testado com Python 3.13.15 no Windows, que traz o SQLite 3.50.4. As consultas pedem o SQLite 3.44 ou mais novo; o script avisa se o seu for mais antigo.

```bash
pip install -r requirements.txt
```

```bash
python scripts/gerar_dados.py
```

```bash
python scripts/limpar_dados.py
```

```bash
python scripts/gerar_gabarito.py
```

```bash
python -m pytest -q
```

Cada passo usa o resultado do anterior:

1. `gerar_dados.py` regrava as duas planilhas de `data/entrada`.
2. `limpar_dados.py` lê as planilhas e grava a versão limpa em `data/limpa`, um CSV por tabela.
3. `gerar_gabarito.py` monta o banco `data/painel.sqlite` com a versão limpa e grava o resultado das seis consultas em `sql/gabarito`.
4. Os testes conferem tudo isso. Os do Power BI abrem o Excel e levam uns 20 minutos; os demais, de um a dois minutos. Sem Excel, os do Power BI são pulados. Para rodar só os demais:

```bash
python -m pytest -q -m "not excel"
```

A mesma semente e a mesma data de referência geram sempre os mesmos arquivos. Para outro cenário:

```bash
python scripts/gerar_dados.py --semente 7 --data-referencia 2026-06-01 --saida ../teste-sst
```

## Os números da geração padrão

Semente 20261101, data de referência 01/11/2026. Todos saem de `python scripts/gerar_dados.py`.

| Medida | Valor |
|---|---|
| Linhas na aba `Controle` | 151 |
| Funcionários únicos | 150 |
| Ativos | 138 |
| Desligados | 12 |
| Linhas com data em texto | 31 |
| Linhas na aba `Historico` | 298 |

Situação dos 1.656 itens dos ativos (138 funcionários x 12 treinamentos):

| Situação | Itens |
|---|---|
| Obrigatórios sem registro | 60 |
| Vencidos | 30 |
| Vencem em até 30 dias | 18 |
| Vencem de 31 a 60 dias | 16 |
| Vencem de 61 a 90 dias | 16 |
| Válidos por mais de 90 dias | 336 |
| Sem vencimento fixo | 363 |
| Condicionais sem data | 681 |
| Não aplicáveis | 135 |
| Com data inválida | 1 |

Esses números conferem a geração. O gabarito, mais abaixo, já aplica a limpeza: a data inválida é descartada, e o item dela passa a contar como sem registro (60 + 1 = 61).

## A versão limpa, em `data/limpa`

Sai de `python scripts/limpar_dados.py`. Um CSV por tabela, em UTF-8 e com datas no formato 2026-11-01.

| Arquivo | Linhas | Conteúdo |
|---|---|---|
| `dim_funcionario.csv` | 150 | Um cadastro por matrícula |
| `dim_funcao.csv` | 5 | As funções |
| `dim_treinamento.csv` | 12 | Código, nome e validade |
| `regra_funcao_treinamento.csv` | 60 | Uma linha por função e treinamento |
| `fato_certificacao.csv` | 1.149 | Uma linha por emissão, juntando `Controle` e `Historico` |
| `parametro.csv` | 1 | Data de referência e janelas |
| `qualidade_rejeicoes.csv` | 2 | O que a limpeza descartou, e por quê |

As duas rejeições são exatamente os dois defeitos que não dá para arrumar: a segunda linha da matrícula 7037 (duplicada) e a data 31/02/2025 da matrícula 7097 na NR-18.

## O gabarito, em `sql/gabarito`

Sai de `python scripts/gerar_gabarito.py`. Cada arquivo é o resultado de uma consulta de `sql/consultas`, com o mesmo nome.

| Consulta | O que responde |
|---|---|
| `01_visao_geral` | Os números de capa: ativos, irregulares, conformidade |
| `02_irregulares_hoje` | Quem está irregular, com quantas pendências e em quais treinamentos |
| `03_vencimentos_30_60_90` | Quantos itens vencem em até 30, 60 e 90 dias |
| `04_agenda_reciclagem` | Cada item que vence nos próximos 90 dias, em ordem de data |
| `05_pendencias_por_funcao` | Pendências e taxa por função |
| `06_pendencias_por_treinamento` | Pendências e taxa por treinamento |

Na data de referência:

| Medida | Valor |
|---|---|
| Funcionários ativos | 138 |
| Funcionários irregulares | 63 |
| Itens obrigatórios | 648 |
| Itens obrigatórios em dia | 560 |
| Conformidade | 86,4% |
| Pendências | 88 (61 sem registro, 27 vencidos) |
| Itens vencidos, contando condicionais | 30 |

O que vence (as janelas somam: "até 60" inclui as de "até 30"):

| Janela | Itens | Obrigatórios | Funcionários |
|---|---|---|---|
| Até 30 dias | 18 | 16 | 17 |
| Até 60 dias | 34 | 32 | 27 |
| Até 90 dias | 50 | 46 | 34 |

Por função, em ordem de taxa de pendência:

| Função | Ativos | Irregulares | Pendências | Taxa | Parte do total |
|---|---|---|---|---|---|
| AJ. DE MONTADOR DE STEEL FRAME | 43 | 25 | 40 | 18,6% | 45,5% |
| MONTADOR DE GESSO | 28 | 15 | 17 | 15,2% | 19,3% |
| MONTADOR DE STEEL FRAME | 53 | 21 | 29 | 10,9% | 33,0% |
| TEC. DE SEGURANÇA DO TRABALHO | 6 | 1 | 1 | 4,2% | 1,1% |
| ENCARREGADO DE OBRAS | 8 | 1 | 1 | 3,1% | 1,1% |

Por treinamento, só os que são obrigatórios para alguma função:

| Treinamento | Obrigatórios | Pendências | Taxa | Parte do total |
|---|---|---|---|---|
| NR-35 | 96 | 23 | 24,0% | 26,1% |
| ASO | 138 | 23 | 16,7% | 26,1% |
| NR-18 | 138 | 20 | 14,5% | 22,7% |
| NR-06 | 138 | 13 | 9,4% | 14,8% |
| NR-01 | 138 | 9 | 6,5% | 10,2% |

A NR-35 e o ASO empatam em número de pendências. A NR-35 fica à frente pela taxa, porque é exigida de menos gente.

### Por que confiar no gabarito

`tests/calculo_pandas.py` refaz as seis respostas por outro caminho: lê as planilhas brutas com pandas, limpa do próprio jeito e faz as contas sem usar a limpeza nem o SQL. O teste `tests/test_gabarito.py` exige que os dois caminhos concordem, também com outra semente e outra data de referência.

## O pacote do Power BI

O painel ainda não está montado: o Power BI Desktop não roda por automação. Está tudo pronto para montar, e [docs/MONTAGEM.md](docs/MONTAGEM.md) diz como, clique a clique, com o número que cada visual tem de mostrar.

| Parte | Onde | O que faz |
|---|---|---|
| Consultas | `powerquery/*.m` | leem as planilhas brutas, limpam, tipam, tiram o duplicado, registram as rejeições e despivotam o `Controle` do formato largo para o longo |
| Modelo | [docs/MODELO.md](docs/MODELO.md) | o modelo em estrela: tabelas, colunas e as sete relações |
| Medidas | `dax/medidas.dax` | as medidas do painel, de "Funcionários Ativos" ao "Status Farol" |
| Tema | `tema/tema.json` | as nove cores do farol e uma paleta neutra |

As quatro páginas: visão geral, matriz farol, agenda de reciclagem e qualidade dos dados.

`tests/test_powerbi.py` monta esse pacote dentro do Excel, que tem os mesmos motores de Power Query e de modelo de dados do Power BI, e confere que as tabelas são iguais às de `data/limpa` e que as medidas dão os números do gabarito. O teste roda duas vezes: com a entrada padrão e com uma entrada mais bagunçada, que também tem itens vencendo em cada fronteira das janelas. Os visuais e as cores na tela ficam para a conferência na montagem.

## Estrutura

```
scripts/gerar_dados.py      gera as duas planilhas
scripts/limpar_dados.py     limpa as planilhas e grava a versão limpa
scripts/gerar_gabarito.py   monta o banco e grava o gabarito
data/entrada/               as planilhas geradas
data/limpa/                 a versão limpa, em CSV
sql/01_tabelas.sql          as tabelas, com as regras que os dados precisam seguir
sql/02_views.sql            as três views: registro vigente, status do item, pendências
sql/consultas/              as seis consultas que respondem à pergunta
sql/gabarito/               o resultado delas, que o painel precisa bater
powerquery/                 uma consulta Power Query por arquivo
dax/medidas.dax             as medidas
tema/tema.json              as cores do painel
tests/                      os testes de cada etapa e o cálculo independente em pandas
docs/COMO-FUNCIONA.md       o projeto explicado sem jargão
docs/DECISOES.md            as escolhas feitas e o porquê
docs/MODELO.md              o modelo de dados do painel
docs/MONTAGEM.md            o passo a passo para montar o painel
```
