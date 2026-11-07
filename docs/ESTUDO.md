# Estudo para entrevista

Dez perguntas prováveis sobre o Painel de Certificações SST, com respostas baseadas no projeto. Os números do painel são os da geração padrão (semente 20261101, data de referência 01/11/2026). Os dos testes são das execuções de 07/11/2026.

## 1. Que problema o projeto resolve?

Numa obra, cada funcionário precisa de exames e treinamentos em dia (ASO, NR-35, NR-18 e outros), e cada um vence depois de um tempo. O controle costuma ficar numa planilha larga, com uma coluna por treinamento, preenchida à mão. O painel responde quatro perguntas: quem está irregular hoje, o que vence nos próximos 30, 60 e 90 dias, qual função concentra as pendências e qual treinamento concentra as pendências.

Na geração padrão, são 138 funcionários ativos e 63 irregulares. A conformidade dos itens obrigatórios é de 86,4% (560 de 648). Nas três janelas, vencem 18, 34 e 50 itens.

Um ponto honesto: os dados são sintéticos. A concentração de pendências nos ajudantes de montador foi colocada no gerador, para o painel ter o que mostrar. Não é um achado sobre uma obra real.

## 2. Como os dados vão da planilha até o painel?

Os dois caminhos partem da mesma planilha bagunçada, em `data/entrada`:

- **Referência, em Python e SQL.** `limpar_dados.py` limpa a planilha e grava um CSV por tabela em `data/limpa`. `gerar_gabarito.py` carrega os CSVs num banco SQLite e grava em `sql/gabarito` o resultado de seis consultas. Esse resultado é o gabarito.
- **O painel, em Power BI.** O Power Query lê as mesmas planilhas brutas e refaz a limpeza por conta própria. O modelo em estrela recebe as tabelas, e 27 medidas DAX fazem as contas das quatro páginas.

O painel não lê a versão limpa, de propósito. Assim, a limpeza do Power Query pode ser conferida contra a limpeza em Python, tabela por tabela.

## 3. Como a limpeza trata os defeitos da planilha?

A aba `Controle` tem quatro defeitos plantados, e cada um tem uma única resposta certa:

| Defeito | O que a limpeza faz |
|---|---|
| Datas gravadas como texto, em 31 linhas | Viram data |
| Espaços sobrando | Saem |
| A matrícula 7037 aparece duas vezes | Fica a primeira linha, e a segunda vai para as rejeições |
| 31/02/2025 na NR-18 da matrícula 7097 | A célula é descartada, e o item passa a contar como sem registro |

Nada some sem deixar rastro. As duas rejeições ficam em `qualidade_rejeicoes.csv`, com o motivo, e aparecem na página de qualidade do painel. A data inválida descarta só a célula, não a linha, porque o resto da linha é válido.

A limpeza também despivota a planilha: em vez de uma coluna por treinamento, fica uma linha por emissão. Juntando `Controle` e `Historico`, são 1.149 linhas. Nesse formato, juntar o histórico e contar fica simples.

Uma matrícula que não é número interrompe a carga, com a aba e a linha na mensagem. Descartar a linha esconderia um funcionário inteiro.

## 4. Como cada item ganha uma situação, e o que é estar irregular?

Um item é um par funcionário ativo e treinamento: 138 × 12 = 1.656 itens. A view `vw_status_item` dá a cada item a primeira situação que se aplica, nesta ordem: não aplicável (a regra da função é NÃO), sem registro, condicional sem registro, sem vencimento, vencido, vence em até 30 dias, de 31 a 60, de 61 a 90 e, por fim, válido.

Irregular é quem tem pelo menos um item obrigatório (regra SIM) sem registro ou vencido. Na data de referência, são 88 pendências: 61 sem registro e 27 vencidas.

O caso delicado é o CONDICIONAL. O treinamento depende de a pessoa exercer certa atividade, e a planilha não diz se ela exerce. Por isso, um item condicional não deixa ninguém irregular e não entra na conformidade. Mas, se a pessoa fez o treinamento e ele está vencendo, o item entra na agenda, porque alguém precisa decidir se renova. Há 3 condicionais vencidos. Por isso o painel mostra 30 itens vencidos e 27 pendências por vencimento.

## 5. Como você calcula o vencimento e as janelas?

O vencimento é a data da emissão mais recente mais a validade em meses, contada como fazem o DATAM do Excel e o EDATE do Power BI. Quando o mês de destino é mais curto, a conta para no último dia dele: 29/02/2024 mais 12 meses dá 28/02/2025. O SQLite sozinho daria 01/03/2025. A view corrige isso, e um teste confere seis casos de fim de mês.

Outros detalhes que mudam números:

- Um item que vence hoje ainda não venceu: fica em "vence em até 30 dias".
- No status de um item, as faixas não se sobrepõem. Na consulta de vencimentos, as janelas somam, porque "até 60 dias" inclui o que vence em até 30. Por isso os números são 18, 34 e 50.
- A data de referência é fixa, 01/11/2026, e não a data de hoje. Assim, os números não mudam de um dia para o outro.
- Os dias das janelas vêm da aba `Alertas`. Trocar 30, 60 e 90 por 15, 45 e 75 muda as contas sem mexer no SQL nem no DAX.

Os dados gerados não tinham nenhum item vencendo exatamente numa fronteira, e trocar `<` por `<=` numa medida passaria nos testes. Por isso, um cenário de teste planta um item em cada fronteira: vence ontem, vence hoje, vence no último dia de cada janela e no dia seguinte.

## 6. Como é o modelo de dados no Power BI?

É um modelo em estrela. No centro fica `fato_certificacao`, com uma linha por emissão. Em volta ficam o funcionário, a função, a equipe, o treinamento e o calendário. São sete relações de um para muitos, todas com filtro em direção única.

Duas escolhas costumam render pergunta:

- **A regra fica numa tabela à parte.** "Itens obrigatórios" conta também o que não tem emissão: quem nunca fez a NR-35 não tem linha na fato. Por isso, a medida conta os funcionários ativos de cada função vezes as regras SIM dela. A fato sozinha não sabe o que falta.
- **Só a emissão vigente conta.** O histórico fica na fato, mas as medidas de situação usam só a emissão vigente. Uma NR-35 de 2021 não deixa ninguém vencido se a de 2024 está em dia.

`parametro` e `qualidade_rejeicoes` ficam soltas. A primeira tem uma linha só, que as medidas leem com `MAX`. A segunda é a lista do que não entrou no modelo e não descreve nenhuma emissão.

## 7. Por que ordenar funções e treinamentos pela taxa, e não pela quantidade?

As funções têm tamanhos muito diferentes: são 53 montadores de steel frame e 6 técnicos de segurança. Pela quantidade de pendências, a função maior pareceria pior só por ser maior. A taxa é a parte dos itens obrigatórios que está pendente.

O ajudante de montador lidera nos dois critérios, com 40 pendências e taxa de 18,6%. Nos treinamentos, a NR-35 e o ASO empatam em quantidade, com 23 cada. A NR-35 fica à frente pela taxa, 24,0% contra 16,7%, porque é exigida de menos gente. As consultas também trazem a parte de cada um no total de pendências, para as duas leituras ficarem à vista.

## 8. Como você sabe que o painel mostra o número certo?

Cada número é calculado por caminhos independentes, e os testes exigem que eles concordem:

1. **SQL contra pandas.** `tests/calculo_pandas.py` lê as planilhas brutas, limpa do próprio jeito e refaz as seis respostas, sem usar a limpeza nem o SQL. Os dois caminhos têm de concordar na geração padrão e também com outra semente e outra data de referência.
2. **Power Query contra Python.** As tabelas do Power Query têm de ser iguais, coluna a coluna, às de `data/limpa`. Isso vale também para uma entrada mais bagunçada, com tabulação no nome, data com hora, regra em minúsculas e outras janelas.
3. **As medidas contra o gabarito, em dois motores.** O primeiro é o Excel, que tem por dentro o mesmo Power Query e o mesmo motor de modelo de dados do Power BI. O segundo é o próprio Power BI Desktop, que abre o projeto, atualiza os dados e responde às mesmas consultas DAX.

Para ver se os testes pegam erro, cada regra do SQL foi quebrada de propósito numa cópia do código, uma de cada vez, e cada quebra derrubou algum teste. No Power BI Desktop, a medida `Vencidos` foi estragada de propósito, e o teste caiu, com 61 irregulares em vez de 63.

São 297 testes em pytest. Num Windows com Excel e Power BI Desktop, `python -m pytest -q --desktop` deu 295 aprovados e 2 pulados de propósito, os das fronteiras, que só valem no cenário variado, em 27 minutos. No GitHub Actions, sem Excel e sem Power BI, 192 passam e 105 são pulados, no Ubuntu com Python 3.11 e 3.13 e no Windows com Python 3.13.

## 9. Por que o projeto do Power BI é gerado por script?

Um painel montado clicando depende de cada clique, e um clique esquecido não fica registrado em lugar nenhum. O formato de projeto do Power BI (PBIP) é todo em texto: o modelo em TMDL e o relatório em PBIR. Por isso, `scripts/montar_pbip.py` escreve o projeto a partir das consultas `.m`, das medidas, das relações e do tema. Não existe uma segunda cópia das medidas que possa ficar diferente da primeira.

O teste exige que `powerbi/` seja exatamente o que o gerador produz, byte a byte. O modelo é lido pela biblioteca do próprio Power BI Desktop, e não por um leitor feito aqui. O custo é que um ajuste feito à mão no Power BI faz o teste cair: o ajuste tem de ir para o gerador.

A conferência na tela ainda achou três problemas que os testes em texto não pegavam. O Desktop recusava um visual porque dois campos dele tinham o mesmo nome interno. Havia textos cortados na visão geral. E uma mensagem de erro culpava a aba quando o problema era a pasta. Os três foram corrigidos no gerador ou no Power Query, e dois deles ganharam teste.

## 10. Quais são as limitações, e o que você mudaria?

As limitações:

- Os dados são sintéticos, e a concentração de pendências vem do gerador.
- As regras de obrigatoriedade são parâmetros do modelo, não interpretação jurídica das NRs. Nove células CONDICIONAL viraram NÃO só para o caso "não aplicável" existir.
- O modelo "farol" de referência tem status de entrega e de assinatura. A planilha só guarda data ou vazio, e o painel mostra só o que os dados sustentam.
- Um número digitado numa célula de data, como 45000, é rejeitado pelo Python e lido como data pelo Power Query, que recebe o mesmo número nos dois casos. Os dados gerados não têm esse caso.
- O PDF mostra só as primeiras linhas da matriz e da agenda, que rolam na tela. O clique nos filtros de equipe e de função não foi conferido na tela.

O que eu mudaria com uma planilha real:

- Primeiro, mediria quanto dela cai nas rejeições e procuraria defeitos que a limpeza ainda não conhece.
- Ligaria os itens CONDICIONAIS a um cadastro de atividades, como a lista de quem trabalha em altura, para eles deixarem de ser um "talvez".
- Para uso diário, publicaria o painel com atualização agendada, o que este projeto não faz.
