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

### Testes independentes do gerador

Os testes rodam o script pela linha de comando e leem as planilhas com um leitor próprio, em `tests/apoio.py`, sem importar nada do gerador. Se o gerador errar uma conta, os testes não herdam o mesmo erro.
