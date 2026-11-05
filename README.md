# Painel de Certificações SST

Projeto em construção. **Até aqui só existe a fase 1: os dados de entrada.** O painel em Power BI vem depois.

A pergunta que o painel vai responder: numa obra com cerca de 150 funcionários, quem está irregular hoje, o que vence nos próximos 30, 60 e 90 dias, e qual função e qual treinamento concentram as pendências?

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

Eles existem para a etapa do Power Query ter o que limpar.

- Datas gravadas como texto em parte das linhas.
- Espaços sobrando em nomes, funções, equipes e datas em texto.
- Um funcionário duplicado: as duas linhas ficam iguais depois da limpeza.
- Uma data que não existe no calendário: 31/02/2025.

## Como reproduzir

Testado com Python 3.13.

```bash
pip install -r requirements.txt
```

```bash
python scripts/gerar_dados.py
```

```bash
python -m pytest -q
```

O segundo comando regrava os dois arquivos e imprime os números abaixo. A mesma semente e a mesma data de referência geram sempre os mesmos dados. Para outro cenário:

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

Esses números servem para conferir a geração. O gabarito oficial do painel, com o tratamento de duplicado e data inválida definido, sai na fase 2.

## Estrutura

```
scripts/gerar_dados.py   gera as duas planilhas
data/entrada/            as planilhas geradas
tests/                   provam que a geração é reproduzível e que os defeitos existem
docs/DECISOES.md         as escolhas feitas e o porquê
```
