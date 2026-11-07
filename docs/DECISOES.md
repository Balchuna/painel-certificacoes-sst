# Decisões

## Fase 1: dados sintéticos

### Uma coluna por treinamento e, ainda assim, histórico

O spec pede as duas coisas, mas uma célula só guarda uma data. A aba `Controle` traz a emissão mais recente de cada item e a aba `Historico` traz as anteriores, em formato longo.

Quem limpar a planilha precisa juntar as duas abas para ter o histórico completo.

### Nove células NÃO que a referência não tem

O spec diz que a `Config_SST` traz SIM, NÃO e CONDICIONAL, mas ela só tem SIM e CONDICIONAL. Sem nenhum NÃO, o caso "não aplicável" nunca apareceria no painel.

Por isso nove células CONDICIONAL viraram NÃO:

| Função | Treinamentos |
|---|---|
| AJ. DE MONTADOR DE STEEL FRAME | NR34 |
| MONTADOR DE GESSO | NR34, PEMT1 |
| TEC. DE SEGURANÇA DO TRABALHO | NR12, NR34, PEMT1, PEMT2, ANDAIME, CARTEIRA |

A escolha é só um parâmetro do modelo, para exercitar o caso. Não é interpretação jurídica das NRs nem afirma nada sobre o que cada função precisa de verdade.

### O que veio da referência

Vieram da `Config_SST` os 5 nomes de função, os 12 códigos de treinamento e as validades em meses, porque o spec pede "os treinamentos da `Config_SST`". São rótulos genéricos, sem dado de pessoa. Nomes, matrículas e datas são todos novos.

O script não lê as referências: os valores estão escritos nele. Assim ninguém precisa da planilha original para reproduzir os dados.

### Só data ou vazio nas células de treinamento

A planilha larga guarda data ou nada. Parte da legenda de 10 status do modelo "farol" não cabe aí: pendências de entrega, assinatura e atualização, e entregue e assinado.

Fica para decidir na fase 2 se o painel mostra só os status que os dados sustentam ou se os dados ganham mais uma coluna.

**Decidido na fase 2:** o painel mostra só os status que os dados sustentam. Ver "Os status de entrega e assinatura ficam fora".

### Data de referência como parâmetro

Vale 2026-11-01 por padrão, o exemplo do spec. Nenhuma conta usa a data de hoje. Sem isso, um mesmo arquivo daria números diferentes a cada dia.

### Arquivos idênticos byte a byte

O Excel guarda dentro do arquivo a hora em que ele foi salvo, e o zip que forma o `.xlsx` também. Com isso, duas gerações iguais dariam arquivos diferentes.

A função `salvar_sem_relogio` troca essas horas pela data de referência. Assim, uma mudança de verdade nos dados aparece no git, e uma nova geração sem mudança não aparece.

Em outro sistema a compactação pode variar. Por isso o teste que confere os arquivos versionados compara célula a célula, e a comparação byte a byte fica entre duas execuções na mesma máquina.

### Defeitos com uma única resposta certa

A limpeza precisa dar um resultado único, senão o gabarito vira opinião:

- As duas linhas do duplicado ficam iguais depois de limpas. Não há como errar qual manter.
- O duplicado fica a 10 linhas ou mais do original, para não ser achado a olho.
- A data inválida cai em item obrigatório de funcionário ativo. Rejeitá-la muda um número do painel.
- Esse item não tem emissão anterior no histórico. Rejeitada a data, ele fica sem registro, sem discussão.
- Em cada linha com data em texto, todas as datas estão em texto. O defeito é por linha, como o spec descreve.

### Só os defeitos pedidos

Cabeçalho na primeira linha, sem linhas de título, sem nomes de função escritos de outro jeito. Inventar outros defeitos daria mais trabalho na limpeza sem que o spec tenha pedido.

### Concentração de pendências é artificial

Os fatores `FATOR_FUNCAO` e `FATOR_EQUIPE` aumentam a chance de pendência dos ajudantes e da Equipe Gama e diminuem a dos técnicos, dos encarregados e da Equipe Alfa. Assim, a pergunta "qual função concentra?" tem resposta. Na geração padrão, a resposta é o ajudante de montador, com taxa de pendência 1,7 vez a das outras funções somadas.

Em qualquer texto sobre o painel, isso deve aparecer como propriedade do gerador, não como descoberta.

Um teste confere essa liderança nos dados publicados. Ele não basta sozinho: na semente padrão, os ajudantes lideram por acaso mesmo sem os fatores. Por isso outro teste gera as sementes 1 a 5, em que, sem os fatores, outra função passa à frente em quatro.

Por treinamento, a concentração não depende de fator: os treinamentos com vencimento acumulam itens vencidos. Na geração padrão, quem lidera é a NR-35.

### A contagem de "Vencidos" do resumo

Os 30 vencidos incluem itens CONDICIONAIS que têm data: se o funcionário fez o treinamento e ele venceu, a conta entra aí. A regra final de como o painel trata esses itens é da fase 2.

**Decidido na fase 2:** os condicionais vencidos aparecem na contagem de itens vencidos (30), mas não viram pendência. As pendências por vencimento são só as dos obrigatórios (27). Ver "CONDICIONAL avisa, mas não pende".

### Testes independentes do gerador

Os testes rodam o script pela linha de comando e leem as planilhas com um leitor próprio, em `tests/apoio.py`, sem importar nada do gerador. Se o gerador errar uma conta, os testes não herdam o mesmo erro.

## Fase 2: SQL de referência e gabarito

### A situação de cada item, nesta ordem

Um item é um par funcionário ativo e treinamento. A view `vw_status_item` dá a ele a primeira situação que se aplica:

| Ordem | Condição | Situação |
|---|---|---|
| 1 | A regra da função é NÃO | Não aplicável |
| 2 | Regra SIM e nenhuma emissão | Sem registro |
| 3 | Regra CONDICIONAL e nenhuma emissão | Condicional sem registro |
| 4 | Treinamento com validade 0 | Sem vencimento |
| 5 | Venceu antes da data de referência | Vencido |
| 6 | Vence em até 30 dias | Vence em até 30 dias |
| 7 | Vence de 31 a 60 dias | Vence em 31 a 60 dias |
| 8 | Vence de 61 a 90 dias | Vence em 61 a 90 dias |
| 9 | O resto | Válido |

Os números 30, 60 e 90 vêm da tabela `parametro`, e os rótulos acompanham. Mudar as janelas na planilha muda as faixas sem mexer no SQL.

### NÃO é sempre "não aplicável"

Mesmo que alguém tenha uma emissão de um treinamento que a função não pede, o item não vence, não avisa e não entra na agenda. Se entrasse, o painel mandaria renovar o que ninguém precisa.

### CONDICIONAL avisa, mas não pende

CONDICIONAL quer dizer que o treinamento depende de a pessoa exercer certa atividade, e a planilha não diz se ela exerce. Por isso:

- não entra na conformidade nem nas pendências: seria cobrar de quem talvez não precise;
- entra na agenda, nas janelas de vencimento e na contagem de itens vencidos quando há data: se a pessoa fez o treinamento, é provável que precise dele, e alguém tem de decidir se renova.

Na data de referência são 3 condicionais vencidos e 4 condicionais na agenda.

### Vence hoje ainda não venceu

Um item que vence na própria data de referência fica em "Vence em até 30 dias", não em "Vencido". Vencido é só o que venceu antes. As janelas e a agenda contam a partir desse dia 0.

### Faixas no status, janelas que somam na consulta

No status de um item, as faixas não se sobrepõem: um item está em "31 a 60" ou em "até 30", nunca nos dois. Na consulta `03_vencimentos_30_60_90`, as janelas somam: "até 60 dias" inclui o que vence em até 30. É assim que a pergunta "o que vence nos próximos 60 dias?" costuma ser feita.

### Vencimento contado como no Excel

O vencimento é a emissão mais recente mais a validade em meses. Quando o mês de destino é mais curto, a conta para no último dia dele: 29/02/2024 mais 12 meses dá 28/02/2025. É o que fazem o DATAM do Excel e o EDATE do Power BI.

O SQLite sozinho daria 01/03/2025. A view corrige isso, e um teste confere seis casos de fim de mês.

### Duplicado: fica a primeira linha

As duas linhas da matrícula duplicada ficam iguais depois de limpas, então tanto faz qual sobra. A primeira é a escolha que não depende de nenhum critério extra. A segunda vai para `qualidade_rejeicoes.csv`.

### Data inválida: descarta a célula, não a linha

A data 31/02/2025 é descartada, mas o resto da linha é válido e fica. O item dela passa a contar como sem registro: o funcionário pode até ter feito o treinamento, mas não há data que prove. A rejeição fica registrada com o valor original.

No `Historico`, uma linha com data inválida não tem mais nada a aproveitar e é descartada inteira. Os dados gerados não têm esse caso, mas a limpeza já o trata.

### As tabelas recusam o que não faz sentido

`sql/01_tabelas.sql` tem regras que a carga precisa cumprir: data no formato certo, matrícula que existe no cadastro, função que tem regra, janelas que crescem, uma linha só de parâmetros. Se a versão limpa quebrar uma delas, a carga para, diz qual arquivo deu problema e apaga o banco pela metade.

A tabela `dim_funcao` existe só para isso: sem ela, um funcionário de uma função sem regra sumiria das contas sem aviso.

### Os status de entrega e assinatura ficam fora

O modelo "farol" tem status como "pendente de assinatura" e "entregue e assinado". A planilha de entrada só guarda data ou vazio, e criar uma coluna para esses status seria inventar dados que o spec não pediu. O painel mostra só as situações da tabela acima.

### Taxa de pendência, não só a quantidade

As funções têm tamanhos muito diferentes: 53 montadores de steel frame, 6 técnicos de segurança. Ordenar pela quantidade de pendências faria a função maior parecer pior só por ser maior. Por isso as consultas 05 e 06 ordenam pela taxa, a parte dos itens obrigatórios que está pendente, e trazem também a parte de cada uma no total de pendências.

Na função, o ajudante de montador lidera nos dois critérios. No treinamento, a NR-35 e o ASO empatam em quantidade (23 cada), e a NR-35 lidera pela taxa.

### Só os treinamentos que alguém precisa ter

A consulta 06 deixa de fora os sete treinamentos que não são SIM para nenhuma função. Sem item obrigatório, a taxa deles seria uma divisão por zero.

### Percentuais com uma casa

O SQL arredonda os percentuais para uma casa decimal, como o painel deve mostrar. O cálculo em pandas guarda o valor exato, e o teste aceita diferença de até 0,05 ponto, o que cabe no arredondamento e em mais nada.

### Um cálculo independente para conferir

`tests/calculo_pandas.py` não usa a versão limpa, o SQL nem os scripts. Lê as planilhas brutas, limpa do próprio jeito e refaz as seis respostas. O teste exige que ele e o SQL concordem nos dados publicados e também com outra semente e outra data de referência.

Para conferir os próprios testes, cada regra acima foi quebrada de propósito numa cópia do código, uma de cada vez. Cada quebra precisa derrubar algum teste além da comparação com os arquivos versionados.

### CSV com o mesmo conteúdo em qualquer sistema

Os CSVs saem em UTF-8 e com fim de linha LF, e o `.gitattributes` mantém o LF no Windows. Assim, uma nova limpeza sem mudança nos dados não aparece no git.
