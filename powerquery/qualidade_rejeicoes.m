// Carregar no modelo: sim
// O que a limpeza deixou de fora e por quê. É a página "Qualidade dos dados" do painel.
//   Matrícula duplicada  a linha repetida do Controle sai inteira (fica a primeira).
//   Data inválida        no Controle, só a célula sai; no Historico, a linha inteira.
//   Data vazia           linha do Historico sem data de emissão.
// "linha" é o número da linha no Excel, para achar o problema na planilha.
// A ordem é a da limpeza em Python: aba Controle linha a linha (e, na linha, coluna a coluna),
// depois a aba Historico.
let
    Duplicadas = List.Transform(
        Table.ToRecords(Table.SelectRows(stg_Controle, each [duplicada])),
        (r) => [
            aba = "Controle", linha = r[linha], ordem = 0, matricula = r[matricula], coluna = "Matrícula",
            valor_original = Text.From(r[matricula]), motivo = "Matrícula duplicada", acao = "Linha descartada"
        ]
    ),
    DatasInvalidas = List.Transform(
        Table.ToRecords(Table.SelectRows(stg_DatasControle, each [invalida])),
        (r) => [
            aba = "Controle", linha = r[linha], ordem = r[posicao] + 1, matricula = r[matricula], coluna = r[coluna],
            valor_original = Text.From(r[valor], "en-US"), motivo = "Data inválida", acao = "Célula descartada"
        ]
    ),
    DoHistorico = List.Transform(
        Table.ToRecords(Table.SelectRows(stg_Historico, each [motivo] <> null)),
        (r) => [
            aba = "Historico", linha = r[linha], ordem = 0, matricula = r[matricula], coluna = "Data de emissão",
            valor_original = if r[motivo] = "Data vazia" then "" else Text.From(r[#"Data de emissão"], "en-US"),
            motivo = r[motivo], acao = "Linha descartada"
        ]
    ),
    Colunas = {"aba", "linha", "ordem", "matricula", "coluna", "valor_original", "motivo", "acao"},
    Tabela = Table.FromRecords(Duplicadas & DatasInvalidas & DoHistorico, Colunas),
    Ordenada = Table.Sort(Tabela, {"aba", "linha", "ordem"}),
    SemOrdem = Table.RemoveColumns(Ordenada, {"ordem"}),
    Tipada = Table.TransformColumnTypes(
        SemOrdem,
        {
            {"aba", type text}, {"linha", Int64.Type}, {"matricula", Int64.Type}, {"coluna", type text},
            {"valor_original", type text}, {"motivo", type text}, {"acao", type text}
        }
    )
in
    Tipada
