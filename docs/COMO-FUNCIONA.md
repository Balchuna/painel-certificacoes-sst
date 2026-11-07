# Como funciona

Este texto explica o projeto sem jargão. Os detalhes técnicos estão no [README](../README.md) e as escolhas, em [DECISOES.md](DECISOES.md).

## O problema

Numa obra, cada funcionário precisa de exames e treinamentos em dia: ASO, NR-35, NR-18 e outros. Cada um vale por um tempo e depois precisa ser refeito. Quem controla isso numa planilha quer saber quatro coisas:

1. quem está irregular hoje;
2. o que vence nos próximos 30, 60 e 90 dias;
3. qual função concentra as pendências;
4. qual treinamento concentra as pendências.

## O caminho dos dados

```
planilha bagunçada  ->  limpeza  ->  versão limpa  ->  banco SQLite  ->  gabarito
data/entrada/           scripts/     data/limpa/       data/            sql/gabarito/
                        limpar_dados.py                painel.sqlite
```

**1. A planilha bagunçada.** Imita o que se vê numa obra: uma coluna por treinamento, datas digitadas como texto, espaços sobrando, um funcionário repetido e uma data que não existe (31 de fevereiro). Os dados são inventados por um script, e nenhum é de pessoa real.

**2. A limpeza.** Arruma o que dá para arrumar e descarta o que não dá:

- espaços sobrando saem;
- "18/11/2023" escrito como texto vira data;
- o funcionário repetido fica uma vez só, com a primeira linha;
- a data 31/02/2025 é descartada, e aquele treinamento fica como "sem registro".

Cada coisa descartada vai para uma lista com o motivo. Nada some sem deixar rastro.

A limpeza também muda o formato. Em vez de uma coluna por treinamento, fica uma linha por emissão: "fulano fez a NR-35 em tal data". Nesse formato, juntar o histórico e contar fica simples.

**3. O banco.** A versão limpa entra num banco SQLite, um arquivo só, sem servidor. As tabelas têm regras: uma data precisa ser data, uma matrícula precisa existir no cadastro. Se algo quebrar uma regra, a carga para e diz qual arquivo deu problema, em vez de seguir com um número errado.

**4. O gabarito.** Seis consultas respondem às quatro perguntas. O resultado de cada uma fica gravado em `sql/gabarito/`. Quando o painel em Power BI ficar pronto, os números dele precisam ser iguais a esses.

**5. O painel.** O Power BI não lê a versão limpa: lê a mesma planilha bagunçada e refaz a limpeza por conta própria, no Power Query, que é a parte do Power BI que prepara os dados. Depois, as medidas fazem as contas, e as quatro páginas mostram o resultado: a visão geral, a matriz farol (um quadro de funcionário por treinamento, pintado pela situação), a agenda de reciclagem e a lista do que a limpeza descartou.

O Power BI não roda sozinho por automação, mas o Excel tem o mesmo Power Query e o mesmo motor de contas por dentro. Os testes montam o painel dentro do Excel e exigem que ele chegue à mesma versão limpa e aos mesmos números do gabarito. O passo a passo para montar no Power BI está em [MONTAGEM.md](MONTAGEM.md).

## Como cada item ganha uma situação

Um item é um par funcionário e treinamento. Para cada funcionário ativo, o banco olha os 12 treinamentos e decide a situação nesta ordem:

1. A regra da função diz NÃO: **não aplicável**. Acabou.
2. Não há nenhuma emissão: **sem registro**, se a regra é SIM; **condicional sem registro**, se a regra é CONDICIONAL.
3. O treinamento não tem validade: **sem vencimento**.
4. Já passou do vencimento: **vencido**.
5. Vence em até 30 dias, de 31 a 60 ou de 61 a 90: um aviso para cada janela.
6. Senão: **válido**.

O vencimento é a data da emissão mais recente mais a validade em meses, contada como no Excel. Por exemplo, uma emissão em 29/02/2024 com validade de 12 meses vence em 28/02/2025.

A conta usa uma data de referência fixa, 01/11/2026, e não a data de hoje. Assim, os números não mudam de um dia para o outro e qualquer pessoa chega ao mesmo resultado.

## O que é estar irregular

Um funcionário está irregular quando tem pelo menos um item **obrigatório** (SIM) sem registro ou vencido.

Um item CONDICIONAL depende de a pessoa exercer certa atividade, e a planilha não diz se ela exerce. Por isso ele não deixa ninguém irregular e não entra na conformidade. Mas, se a pessoa fez o treinamento e ele está vencendo, o item aparece na agenda de reciclagem, porque alguém precisa decidir se renova.

## Os números na data de referência

| Pergunta | Resposta |
|---|---|
| Funcionários ativos | 138 |
| Irregulares hoje | 63 |
| Conformidade dos itens obrigatórios | 86,4% (560 de 648) |
| Vencem nos próximos 30 / 60 / 90 dias | 18 / 34 / 50 itens |
| Função com maior taxa de pendência | ajudante de montador, 18,6% |
| Treinamento com maior taxa de pendência | NR-35, 24,0% |

A concentração nos ajudantes foi colocada de propósito no gerador de dados, para o painel ter o que mostrar. Não é descoberta sobre uma obra real.

## Por que confiar no gabarito

Os mesmos números são calculados uma segunda vez, por outro caminho: um programa em pandas que lê a planilha bagunçada direto, limpa do próprio jeito e refaz as contas, sem usar a limpeza nem o SQL. Os testes exigem que os dois caminhos concordem. Para um erro passar, ele teria de acontecer igual nos dois.

Os testes também repetem tudo com outra semente e outra data de referência, para mostrar que o acordo não depende dos dados publicados.
