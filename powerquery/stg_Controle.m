// Carregar no modelo: não (desmarque "Habilitar carga")
// A aba Controle, uma linha por linha do Excel, com a matrícula já convertida em número.
// A coluna "duplicada" marca a segunda (ou terceira...) linha de uma matrícula repetida:
// fica a primeira ocorrência e a repetida sai inteira, inclusive as datas, como na limpeza em Python.
// Se alguma matrícula não for número, a atualização para e diz a linha.
let
    Aba = fn_LerAba("controle_largo.xlsx", "Controle"),
    ComMatricula = Table.AddColumn(
        Aba, "matricula", each fn_LerMatricula([#"Matrícula"], "Controle, linha " & Text.From([linha])), Int64.Type
    ),
    ComErro = Table.SelectRowsWithErrors(ComMatricula, {"matricula"}),
    Conferida = if Table.IsEmpty(ComErro) then ComMatricula else error (try ComErro{0}[matricula])[Error],
    // A linha onde cada matrícula aparece pela primeira vez.
    Primeiras = List.Buffer(
        Table.Group(Conferida, {"matricula"}, {{"primeira", each List.Min([linha]), Int64.Type}})[primeira]
    ),
    ComDuplicada = Table.AddColumn(Conferida, "duplicada", each not List.Contains(Primeiras, [linha]), type logical)
in
    ComDuplicada
