# Como montar o painel no Power BI Desktop

Este é o passo a passo para montar o painel do zero, clique a clique. Cada etapa diz o que fazer e por quê. Tudo o que você vai colar já está pronto no repositório:

| O quê | Onde |
|---|---|
| As 19 consultas do Power Query | [`powerquery/`](../powerquery), um arquivo `.m` por consulta |
| As medidas | [`dax/medidas.dax`](../dax/medidas.dax) |
| As cores | [`tema/tema.json`](../tema/tema.json) |
| O desenho do modelo | [MODELO.md](MODELO.md) |
| Os números que o painel tem de mostrar | [`sql/gabarito/`](../sql/gabarito) |

Os números citados aqui são os da geração padrão (semente 20261101, data de referência 01/11/2026). Se você gerou outro cenário, compare com o seu `sql/gabarito/`.

Conte com uma a duas horas na primeira vez. A maior parte é colar consultas e arrastar campos.

> Os nomes dos menus estão como aparecem no Power BI Desktop em português. Se a sua versão mostrar um nome um pouco diferente, procure pelo sentido: os menus mudam de lugar de uma versão para outra, as etapas não.

## O atalho: abrir o projeto pronto

O repositório já traz o painel montado, em `powerbi/`, gerado por `scripts/montar_pbip.py` a partir das mesmas peças deste passo a passo. Para usá-lo:

1. Gere uma cópia fora do repositório, apontando para a sua pasta de entrada:

   ```bash
   python scripts/montar_pbip.py --pasta-entrada "D:\Repos\painel-certificacoes-sst\data\entrada" --saida ../painel-local
   ```

   *Por quê:* o caminho da pasta fica gravado no projeto. Na cópia vai o seu caminho; o `powerbi/` do repositório guarda só um caminho de exemplo, para o nome do seu usuário do Windows não ir para o git.
2. No Power BI Desktop, **Arquivo > Abrir** e escolha `PainelSST.pbip` na pasta `painel-local`.
3. Clique em **Página Inicial > Atualizar**. Se aparecer um aviso sobre a pasta, confira o caminho em **Página Inicial > Transformar dados > Editar parâmetros > PastaEntrada**.
4. Confira as quatro páginas com os números dos passos 7 a 10.
5. Exporte o PDF e as imagens como no passo 12.

O resto deste guia monta o mesmo painel do zero. Serve para entender cada peça, ou se o projeto pronto não abrir na sua versão do Power BI.

Se você ajustar o painel no Power BI e quiser guardar o ajuste no repositório, saiba que `tests/test_pbip.py` exige que `powerbi/` seja exatamente o que o gerador produz. O ajuste precisa ir para `scripts/montar_pbip.py`, ou o teste acusa a diferença.

## 1. Antes de começar

1. Instale o Power BI Desktop. É gratuito e só existe para Windows. O caminho mais simples é a Microsoft Store: procure "Power BI Desktop" e clique em **Obter**.
   *Por quê:* pela Store ele se atualiza sozinho.
2. Confira que as planilhas de entrada existem em `data/entrada`: `controle_largo.xlsx` e `parametros.xlsx`. Se não existirem, gere-as com `python scripts/gerar_dados.py`.
3. Anote o caminho completo dessa pasta, por exemplo `D:\Repos\painel-certificacoes-sst\data\entrada`.
   *Por quê:* é o único endereço que o painel precisa conhecer. Todas as consultas leem dali.

## 2. Criar o arquivo e desligar as adivinhações

1. Abra o Power BI Desktop e crie um relatório em branco.
2. Vá em **Arquivo > Opções e configurações > Opções**. Em **ARQUIVO ATUAL > Carregamento de Dados**:
   - desmarque **Data/hora automática**;
   - desmarque **Detectar automaticamente novas relações após o carregamento dos dados**.
3. Clique em **OK**.

*Por quê:* a data/hora automática cria uma tabela de datas escondida para cada coluna de data, e o modelo já tem a sua, `dim_calendario`. A detecção automática de relações tenta adivinhar ligações pelo nome das colunas e erraria aqui: `funcao` aparece em três tabelas. As sete relações certas você cria à mão no passo 4.

## 3. As consultas (Power Query)

### 3.1 Como criar cada consulta

1. Na faixa **Página Inicial**, clique em **Transformar dados**. Abre o Editor do Power Query.
2. No editor, clique em **Nova Fonte > Consulta Nula** (em algumas versões, **Outras fontes > Consulta Nula** ou **Consulta em branco**).
3. Clique em **Editor Avançado**, apague o que estiver lá e cole o conteúdo inteiro do arquivo `.m`. Clique em **Concluído**.
4. No painel **Consultas**, à esquerda, clique com o botão direito na consulta nova, escolha **Renomear** e dê a ela exatamente o nome do arquivo, sem o `.m`: `fn_LimparTexto`, `dim_funcionario` e assim por diante.

*Por quê do nome exato:* as consultas se chamam umas às outras pelo nome. `fato_certificacao` lê `dim_treinamento`; se o nome tiver uma letra diferente, ela não acha e dá erro.

A primeira linha de cada arquivo diz se a consulta vai para o modelo: `// Carregar no modelo: sim` ou `não`.

### 3.2 A ordem

Crie nesta ordem: cada uma usa só as que vêm antes. Fora de ordem também funciona, mas a consulta mostra erro até a que ela usa existir.

| # | Consulta | Carregar? | O que faz |
|---|---|---|---|
| 1 | `PastaEntrada` | não | o parâmetro com a pasta das planilhas |
| 2 | `fn_LimparTexto` | não | tira espaços sobrando e espaços estranhos de um texto |
| 3 | `fn_LerData` | não | lê uma célula de data (data do Excel ou dd/mm/aaaa) |
| 4 | `fn_LerMatricula` | não | lê a matrícula e para tudo se ela não for um número |
| 5 | `Arquivos` | não | lista as planilhas da pasta |
| 6 | `fn_LerAba` | não | abre uma aba de uma planilha, com o cabeçalho limpo |
| 7 | `dim_treinamento` | sim | os treinamentos e a validade de cada um |
| 8 | `dim_funcao` | sim | as funções |
| 9 | `regra_funcao_treinamento` | sim | SIM, NÃO ou CONDICIONAL por função e treinamento |
| 10 | `parametro` | sim | data de referência e janelas de alerta |
| 11 | `stg_Controle` | não | a aba Controle lida, com a marca de linha duplicada |
| 12 | `stg_DatasControle` | não | as datas do Controle, despivotadas (uma linha por célula) |
| 13 | `stg_Historico` | não | a aba Historico lida, com o motivo de cada rejeição |
| 14 | `dim_funcionario` | sim | um funcionário por matrícula |
| 15 | `dim_equipe` | sim | as equipes, para o filtro |
| 16 | `fato_certificacao` | sim | uma linha por emissão, com vencimento e emissão vigente |
| 17 | `qualidade_rejeicoes` | sim | o que a limpeza deixou de fora e por quê |
| 18 | `dim_calendario` | sim | um dia por linha |
| 19 | `Medidas` | sim | tabela vazia que guarda as medidas |

### 3.3 O parâmetro da pasta

Na consulta `PastaEntrada`, troque o texto `C:\caminho\do\projeto\data\entrada` pelo caminho que você anotou no passo 1, mantendo as aspas. Ao clicar em **Concluído**, ela aparece com o ícone de parâmetro.

*Por quê:* se a pasta mudar de lugar, você troca o caminho num lugar só (**Página Inicial > Gerenciar Parâmetros**), e as outras 18 consultas acompanham.

### 3.4 Desligar a carga das etapas intermediárias

Clique com o botão direito em `Arquivos`, `stg_Controle`, `stg_DatasControle` e `stg_Historico`, uma de cada vez, e desmarque **Habilitar carga**. Confira que `PastaEntrada` também está desmarcada. As funções (`fn_...`) não têm essa opção: função nunca vai para o modelo.

*Por quê:* essas consultas são passos do caminho, não tabelas do painel. Carregadas, elas duplicariam os dados no arquivo e poluiriam a lista de campos.

Opcional: selecione as consultas com Ctrl, clique com o botão direito e use **Mover para o grupo > Novo grupo** para separar "Funções", "Etapas" e "Modelo". Só ajuda a achar as coisas.

### 3.5 Carregar e conferir

1. Clique em **Fechar e Aplicar**.
2. Na **Exibição de tabela** (o ícone de grade na lateral esquerda), clique em cada tabela e confira o número de linhas no rodapé:

| Tabela | Linhas |
|---|---|
| `dim_funcionario` | 150 |
| `dim_funcao` | 5 |
| `dim_equipe` | 3 |
| `dim_treinamento` | 12 |
| `regra_funcao_treinamento` | 60 |
| `fato_certificacao` | 1149 |
| `dim_calendario` | 2192 |
| `parametro` | 1 |
| `qualidade_rejeicoes` | 2 |
| `Medidas` | 0 |

*Por quê:* essas são as mesmas contagens da versão limpa em CSV (`data/limpa/`, mais as três tabelas que só existem no painel). Se uma delas não bate, o problema está na consulta, e é muito mais fácil achar agora do que depois, num gráfico.

## 4. O modelo

Abra a **Exibição de modelo** (o terceiro ícone da lateral esquerda). O desenho de referência está em [MODELO.md](MODELO.md).

### 4.1 As sete relações

Em **Página Inicial > Gerenciar relações > Nova relação**, crie uma por linha. Em todas: cardinalidade **Muitos para um (\*:1)**, direção do filtro cruzado **Única**, e **Tornar esta relação ativa** marcado.

| De (muitos) | Para (um) |
|---|---|
| `dim_funcionario[funcao]` | `dim_funcao[funcao]` |
| `dim_funcionario[equipe]` | `dim_equipe[equipe]` |
| `fato_certificacao[matricula]` | `dim_funcionario[matricula]` |
| `fato_certificacao[treinamento]` | `dim_treinamento[codigo]` |
| `regra_funcao_treinamento[funcao]` | `dim_funcao[funcao]` |
| `regra_funcao_treinamento[treinamento]` | `dim_treinamento[codigo]` |
| `fato_certificacao[data_vencimento]` | `dim_calendario[data]` |

`parametro`, `qualidade_rejeicoes` e `Medidas` ficam soltas.

*Por quê:* são as relações que deixam um filtro de função, equipe ou treinamento chegar às emissões. Direção única evita caminhos ambíguos entre as tabelas. O porquê de cada uma está em [MODELO.md](MODELO.md#relacionamentos).

### 4.2 Tabela de datas

Selecione `dim_calendario` e use **Ferramentas de tabela > Marcar como tabela de datas**, escolhendo a coluna `data`.

*Por quê:* diz ao Power BI que essa é a régua de tempo do modelo. É o que habilita as funções de tempo do DAX e garante que nenhum dia falta no eixo.

### 4.3 Ordem de classificação

1. Selecione a coluna `dim_treinamento[codigo]` e use **Ferramentas de coluna > Classificar por coluna > ordem**.
2. Selecione `dim_calendario[mes_ano]` e classifique por `ano_mes`.

*Por quê:* sem isso, a matriz põe os treinamentos em ordem alfabética (ANDAIME primeiro, ASO depois) em vez da ordem da planilha, e o gráfico põe "abr/2027" antes de "dez/2026".

### 4.4 Números que não são para somar

Para cada coluna abaixo, selecione-a e mude **Ferramentas de coluna > Resumo** para **Não resumir**:

`dim_funcionario[matricula]`, `fato_certificacao[matricula]`, `qualidade_rejeicoes[matricula]`, `qualidade_rejeicoes[linha]`, `dim_treinamento[validade_meses]`, `dim_treinamento[ordem]`, `dim_calendario[ano]`, `dim_calendario[mes]`, `dim_calendario[ano_mes]`, `dim_calendario[meses_da_referencia]`, `parametro[janela_1]`, `parametro[janela_2]` e `parametro[janela_3]`.

*Por quê:* o Power BI soma toda coluna de número quando ela vai para um visual. Somar matrículas ou números de linha não tem sentido; com "Não resumir", a tabela mostra cada matrícula como ela é.

### 4.5 Esconder o que é só engrenagem

Clique com o botão direito e escolha **Ocultar na exibição de relatório** para: `Medidas[oculta]`, `dim_treinamento[ordem]` e `dim_calendario[ano_mes]`.

*Por quê:* `oculta` só existe porque toda tabela precisa de uma coluna; escondida, a tabela `Medidas` passa a aparecer no topo da lista de campos, com o ícone de calculadora. As outras duas só servem para ordenar.

## 5. As medidas

### 5.1 Pela exibição de consulta DAX (o caminho mais rápido)

1. Abra a **Exibição de consulta DAX** (o quarto ícone da lateral esquerda).
2. Cole o conteúdo inteiro de `dax/medidas.dax` e clique em **Executar**.
3. Confira o resultado com `sql/gabarito/01_visao_geral.csv`: 01/11/2026, 138 funcionários ativos, 63 irregulares, 648 itens obrigatórios, 560 válidos, 0,864 de conformidade (86,4%), 88 pendentes, 61 sem registro, 27 obrigatórios vencidos e 30 vencidos.
4. Acima de cada `MEASURE` aparece o link **Atualizar modelo: Adicionar nova medida**. Use o botão **Atualizar modelo com alterações**, no alto, para adicionar todas de uma vez.

*Por quê:* rodar antes de adicionar mostra, numa linha, se as medidas batem com o gabarito do SQL. Se não batem, o erro está no modelo (uma relação faltando, a direção errada), e você descobre antes de montar qualquer gráfico.

### 5.2 À mão, se a exibição de consulta DAX não aparecer

Selecione a tabela `Medidas`, clique em **Nova medida** e cole uma medida por vez, no formato `Nome = expressão`: por exemplo, `Funcionários Ativos = CALCULATE ( COUNTROWS ( dim_funcionario ), ... )`. Siga a ordem do arquivo, porque cada medida usa as anteriores. Depois, crie uma tabela visual com as dez medidas do `EVALUATE` do fim do arquivo e confira com o gabarito, como no passo anterior.

### 5.3 O que cada medida faz

| Medida | O que mostra |
|---|---|
| `Data de Referência` | a data de referência da aba Alertas |
| `Funcionários Ativos` | quantos funcionários com situação Ativo |
| `Itens Obrigatórios` | cada ativo vezes cada treinamento SIM da função dele |
| `Obrigatórios com Registro` | itens obrigatórios que têm emissão |
| `Itens com Vencimento` | emissões vigentes, SIM ou CONDICIONAL, que vencem |
| `Vencidos` | itens que venceram antes da data de referência |
| `Obrigatórios Vencidos` | o mesmo, só os obrigatórios |
| `Vencem em 30 dias` | vencem da data de referência até o fim da janela 1 |
| `Vencem em 60 dias` | até o fim da janela 2 (inclui os de 30) |
| `Vencem em 90 dias` | até o fim da janela 3 (inclui os de 30 e 60) |
| `Itens Válidos` | obrigatórios com emissão e ainda não vencidos |
| `Pendentes Obrigatórios` | obrigatórios sem emissão ou vencidos |
| `Obrigatórios Sem Registro` | obrigatórios sem emissão nenhuma |
| `% Conformidade` | válidos ÷ obrigatórios |
| `% Pendência` | pendentes ÷ obrigatórios |
| `Funcionários Irregulares` | ativos com pelo menos uma pendência obrigatória |
| `Item Único` | verdadeiro quando o contexto é um funcionário num treinamento |
| `Regra do Item` | a regra desse item |
| `Emissão do Item` | a data da emissão vigente |
| `Vencimento do Item` | a data de vencimento da emissão vigente |
| `Dias para Vencer` | dias até o vencimento; negativo quando já venceu |
| `Código Farol` | a situação do item como número, de 1 (vencido) a 9 (não aplicável) |
| `Status Farol` | a situação em texto, igual à do SQL |
| `Cor Farol` | a cor de fundo da célula |
| `Rótulo Farol` | o texto da célula: a data de vencimento ou uma palavra curta |
| `Na Agenda` | 1 quando o item vence dentro da maior janela |
| `Linhas Rejeitadas` | quantas coisas a limpeza deixou de fora |

Os nomes "30, 60 e 90 dias" são fixos. Os dias de verdade vêm da aba Alertas: se ela disser 15, 45 e 75, as medidas contam 15, 45 e 75, com o mesmo nome.

### 5.4 Formatos

Selecione cada medida e ajuste em **Ferramentas de medida > Formatar**:

- `% Conformidade` e `% Pendência`: **Porcentagem**, uma casa decimal.
- `Data de Referência`, `Emissão do Item` e `Vencimento do Item`: **Data**, no formato dd/mm/aaaa.
- As contagens e `Dias para Vencer`: **Número inteiro**.

Opcional: oculte `Item Único`, que só serve às outras medidas.

*Por quê:* sem formato, a conformidade aparece como 0,864 e as datas com hora.

### 5.5 Vazio em vez de zero

Quando não há nada a contar, as medidas devolvem vazio, e não zero: escolha uma equipe sem nenhum vencido, e o cartão de vencidos mostra "(Em branco)". É de propósito: se `Vencidos` devolvesse 0, a matriz e as tabelas passariam a mostrar uma linha para cada combinação possível, mesmo as que não têm nada. Se quiser zero num cartão específico, crie uma medida só para ele, como `Vencidos (cartão) = [Vencidos] + 0`, e use-a só no cartão.

## 6. O tema

Na faixa **Exibição**, abra a lista de **Temas**, clique em **Procurar temas** e escolha `tema/tema.json`.

*Por quê:* o tema põe a paleta neutra (azuis e cinzas) nos gráficos comuns e as nove cores do farol na mesma ordem do `Código Farol`. As cores do farol são as mesmas da medida `Cor Farol`, então legenda, matriz e agenda falam a mesma língua: vermelho é vencido, amarelo é "vence logo", verde é válido.

| Código | Situação | Cor |
|---|---|---|
| 1 | Vencido | `#E06666` vermelho |
| 2 | Sem registro (obrigatório) | `#C27BA0` roxo |
| 3 | Vence em até 30 dias | `#F6B26B` laranja |
| 4 | Vence em 31 a 60 dias | `#FFD966` amarelo |
| 5 | Vence em 61 a 90 dias | `#FFF2CC` amarelo-claro |
| 6 | Válido | `#93C47D` verde |
| 7 | Sem vencimento | `#B6D7A8` verde-claro |
| 8 | Condicional sem registro | `#D9D9D9` cinza |
| 9 | Não aplicável | `#F3F3F3` cinza-claro |

## 7. Página 1: Visão geral

Renomeie a primeira página para "Visão geral" (clique duplo na aba, embaixo).

**Os cartões.** Insira um visual **Cartão** para cada medida abaixo e arraste a medida para o campo do cartão.

| Cartão | Medida | Deve mostrar |
|---|---|---|
| Data de referência | `Data de Referência` | 01/11/2026 |
| Funcionários ativos | `Funcionários Ativos` | 138 |
| Funcionários irregulares | `Funcionários Irregulares` | 63 |
| Conformidade | `% Conformidade` | 86,4% |
| Pendentes obrigatórios | `Pendentes Obrigatórios` | 88 |
| Vencidos | `Vencidos` | 30 |
| Vencem em 30 dias | `Vencem em 30 dias` | 18 |
| Vencem em 60 dias | `Vencem em 60 dias` | 34 |
| Vencem em 90 dias | `Vencem em 90 dias` | 50 |

*Por quê:* é a resposta direta à primeira pergunta do painel, "quem está irregular hoje e o que vence logo". Os números vêm de `01_visao_geral.csv` e `03_vencimentos_30_60_90.csv`.

*Para caber:* com nove cartões numa fila, a data e os rótulos longos aparecem cortados. O projeto pronto põe o cartão da data no alto, ao lado do título, e os outros oito numa fila. Os rótulos usam fonte 9, em **Formatar > Rótulo da categoria**.

**% conformidade por função.** Insira um **Gráfico de barras clusterizado**: `dim_funcao[funcao]` no eixo Y e `% Conformidade` no eixo X. Em **Mais opções (...) > Classificar eixo**, escolha `% Conformidade` e **Classificar em ordem crescente**.

*Por quê:* em ordem crescente, a função com mais problema fica no alto. Deve começar por AJ. DE MONTADOR DE STEEL FRAME com 81,4% e terminar em ENCARREGADO DE OBRAS com 96,9% (`05_pendencias_por_funcao.csv`). Se o nome da função aparecer cortado, aumente **Formatar > Eixo Y > Valores > Largura máxima** (o projeto pronto usa 45%).

**Vencimentos por mês.** Insira um **Gráfico de colunas clusterizado**: `dim_calendario[mes_ano]` no eixo X e `Itens com Vencimento` no eixo Y. No painel **Filtros**, em **Filtros neste visual**, arraste `dim_calendario[meses_da_referencia]`, escolha **Filtragem avançada** e use "é maior ou igual a 0" **e** "é menor ou igual a 11".

*Por quê:* mostra os próximos doze meses a partir da data de referência, e o filtro anda sozinho quando a data muda na planilha. Os primeiros meses devem mostrar 17 (nov/2026), 17 (dez/2026), 17 (jan/2027) e 20 (fev/2027). O mês da data de referência aparece inteiro: se a data fosse dia 15, o que venceu do dia 1 ao dia 14 também entraria na primeira coluna.

**Filtros da página.** Insira duas **Segmentações de dados**, uma com `dim_equipe[equipe]` e outra com `dim_funcao[funcao]`.

*Por quê:* o encarregado de uma equipe quer ver só a dele; os cartões e os gráficos acompanham.

## 8. Página 2: Matriz farol

Crie uma página nova e chame-a de "Matriz farol".

1. Insira um visual **Matriz**.
2. Em **Linhas**, `dim_funcionario[funcionario]` (matrícula e nome). Em **Colunas**, `dim_treinamento[codigo]`. Em **Valores**, `Rótulo Farol`.
3. Em **Formatar visual > Elementos de célula**, escolha a série `Rótulo Farol`, ligue **Cor da tela de fundo** e clique em **fx**. Em **Estilo do formato**, escolha **Valor do campo**; em **Em qual campo devemos basear isso?**, escolha `Cor Farol`. Clique em **OK**.
4. Em **Formatar visual > Subtotais de linha** e **Subtotais de coluna**, desligue os dois.
5. Em **Filtros neste visual**, arraste `dim_funcionario[situacao]` e marque só **Ativo**.
6. Copie as duas segmentações da página 1 (Ctrl+C, Ctrl+V). Quando o Power BI perguntar, escolha **Sincronizar**.

*Por quê:* é a planilha original, mas lida de relance. Cada linha é um funcionário, cada coluna um treinamento, e a cor diz a situação; o texto diz quando vence ou o que falta ("falta", "cond.", "sem venc.", "n/a"). A linha usa `funcionario` e não `nome` para dois homônimos não virarem uma linha só. Os totais não têm sentido para um rótulo de texto. O filtro de ativos deixa claro que desligado não entra. Sincronizar faz a escolha de equipe valer nas duas páginas.

Deve aparecer uma linha por funcionário ativo (138) e uma coluna por treinamento (12), na ordem da planilha: ASO, NR01, NR05, NR06, NR12, NR18, NR34, NR35, PEMT1, PEMT2, ANDAIME e CARTEIRA. Para conferir uma linha, procure 7052: tem de ter ASO, NR06, NR18 e NR35 em vermelho ou roxo (`02_irregulares_hoje.csv`, primeira linha).

**Legenda.** A matriz não tem legenda própria. Insira uma **Caixa de texto** acima dela e escreva as nove situações da tabela do passo 6, cada uma precedida de ■, pintando cada ■ com a cor dela.

**Opcional: só quem tem pendência.** Em **Filtros neste visual**, arraste `dim_funcionario[funcionario]`, escolha **Filtragem básica > Mostrar itens quando o valor**, e use `Pendentes Obrigatórios` "é maior que" 0. A matriz cai para 63 linhas, os irregulares.

## 9. Página 3: Agenda de reciclagem

Crie uma página nova e chame-a de "Agenda de reciclagem".

1. Insira um visual **Tabela** com, nesta ordem: `Vencimento do Item`, `Dias para Vencer`, `dim_funcionario[matricula]`, `dim_funcionario[nome]`, `dim_funcionario[funcao]`, `dim_funcionario[equipe]`, `dim_treinamento[codigo]`, `dim_treinamento[nome]`, `Emissão do Item` e `Status Farol`.
2. Em **Filtros neste visual**, arraste a medida `Na Agenda` e use "é" 1.
3. Clique no cabeçalho **Vencimento do Item** para ordenar do mais próximo para o mais distante.
4. Em **Formatar visual > Elementos de célula**, escolha a série `Status Farol`, ligue **Cor da tela de fundo**, **fx**, **Valor do campo**, `Cor Farol`.
5. Copie as segmentações de equipe e função da página 1 e sincronize.

*Por quê:* é a lista de trabalho da semana: quem precisa refazer o quê, do vencimento mais próximo ao mais distante. O filtro `Na Agenda` deixa só o que vence da data de referência até o fim da maior janela; o que já venceu está na matriz e nos cartões, não aqui. Os filtros são de equipe e de função, para que cada encarregado veja a agenda da sua turma.

Devem aparecer 50 linhas, as mesmas de `04_agenda_reciclagem.csv`. As duas primeiras vencem em 10/11/2026, faltando 9 dias: 7061 na PEMT2 e 7076 no ASO.

## 10. Página 4: Qualidade dos dados

Crie uma página nova e chame-a de "Qualidade dos dados".

1. Insira um **Cartão** com `Linhas Rejeitadas`. Deve mostrar 2.
2. Insira uma **Tabela** com as colunas de `qualidade_rejeicoes`: `aba`, `linha`, `matricula`, `coluna`, `valor_original`, `motivo` e `acao`.
3. Insira um **Gráfico de barras clusterizado** com `qualidade_rejeicoes[motivo]` no eixo Y e `Linhas Rejeitadas` no eixo X.
4. Insira uma **Caixa de texto** com: "Cada linha é algo que a limpeza deixou de fora. Corrija na planilha de origem e clique em Atualizar."

*Por quê:* um painel que descarta dados sem avisar engana. Aqui fica à vista o que não entrou, em que linha do Excel está e o que foi feito: a linha inteira descartada ou só a célula. Com a entrada padrão, são duas: a matrícula 7037 repetida na linha 68 e a data 31/02/2025 na NR18 da matrícula 7097, linha 99.

## 11. Atualizar com dados novos

1. Gere ou edite as planilhas em `data/entrada`.
2. No Power BI, clique em **Página Inicial > Atualizar**.

Para mudar a data de referência ou as janelas, edite a aba `Alertas` de `parametros.xlsx` e atualize. Os cartões, a matriz e a agenda acompanham, e os títulos "Vence em até N dias" do `Status Farol` mudam junto.

*Por quê:* nada no painel tem data ou número de dias escrito à mão; tudo sai de `parametro`.

## 12. Salvar e exportar

1. **Arquivo > Salvar como**. Se a lista de tipos tiver **Arquivos de projeto do Power BI (\*.pbip)**, prefira esse formato e salve numa pasta `powerbi/` do repositório. Se não tiver, salve como `.pbix`.
   *Por quê:* o PBIP guarda o relatório e o modelo em arquivos de texto, que o git compara linha a linha; o `.pbix` é um arquivo fechado. O Power BI cria sozinho um `.gitignore` dentro da pasta do projeto, para o cache e as configurações locais não irem para o repositório.
2. Antes de pôr o PBIP no git, confira o caminho gravado no parâmetro `PastaEntrada`: ele vai junto. Um caminho como `D:\Repos\...` não diz nada; um que passa pela pasta `Users` do Windows mostra o nome do usuário do computador.
3. **Arquivo > Exportar > Exportar em PDF** gera um PDF com as quatro páginas. O Power BI grava o PDF numa pasta temporária e o abre; salve uma cópia em `docs/painel/painel.pdf`.
   *Atenção:* a matriz e a agenda têm barra de rolagem, e o PDF mostra só as linhas que cabem na página.
4. Para as imagens, rode `python scripts/imagens_do_pdf.py`. Ele grava em `docs/painel/` uma imagem PNG de cada página do PDF.
   *Por quê:* a imagem que sai do PDF tem sempre o mesmo tamanho e não leva pedaços da tela, como a barra de tarefas ou outra janela aberta. E dá para refazer com um comando.

## 13. Se algo der errado

| O que aparece | O que costuma ser |
|---|---|
| "A importação X não corresponde a nenhuma exportação" ou "O nome X não foi reconhecido" | a consulta X não existe ou foi renomeada com outra grafia |
| "Arquivo não encontrado: Não consegui ler controle_largo.xlsx na pasta..." | `PastaEntrada` aponta para a pasta errada, ou o arquivo não está nela |
| "Matrícula inválida" com o número da linha | a planilha tem uma matrícula que não é número; a carga para de propósito, porque sem matrícula não dá para saber de quem é a linha |
| "não é SIM, NÃO nem CONDICIONAL" | uma célula da aba `Regra_Funcao_Treinamento` tem outro valor |
| Uma tabela com o número de linhas errado no passo 3.5 | compare a consulta com o arquivo `.m`; uma etapa pode ter ficado de fora ao colar |
| Os números do passo 5.1 não batem | confira as sete relações (direção **Única**, todas ativas) e se `dim_calendario` está marcada como tabela de datas |
| O cartão mostra "(Em branco)" | não há nada a contar com o filtro atual; ver o passo 5.5 |
