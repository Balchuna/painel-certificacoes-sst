// Carregar no modelo: não (desmarque "Habilitar carga")
// A aba Historico: uma emissão anterior por linha. A coluna "motivo" diz por que uma linha não
// vira emissão: "Data inválida" ou "Data vazia". Linha com motivo vazio é emissão boa.
let
    Aba = fn_LerAba("controle_largo.xlsx", "Historico"),
    ComMatricula = Table.AddColumn(
        Aba, "matricula", each fn_LerMatricula([#"Matrícula"], "Historico, linha " & Text.From([linha])), Int64.Type
    ),
    ComErro = Table.SelectRowsWithErrors(ComMatricula, {"matricula"}),
    Conferida = if Table.IsEmpty(ComErro) then ComMatricula else error (try ComErro{0}[matricula])[Error],
    ComTreinamento = Table.AddColumn(Conferida, "treinamento", each fn_LimparTexto([Treinamento]), type text),
    Lida = Table.AddColumn(ComTreinamento, "leitura", each try fn_LerData([#"Data de emissão"])),
    ComData = Table.AddColumn(
        Lida, "data", each if [leitura][HasError] then null else [leitura][Value], type nullable date
    ),
    ComMotivo = Table.AddColumn(
        ComData,
        "motivo",
        each if [leitura][HasError] then "Data inválida" else if [data] = null then "Data vazia" else null,
        type nullable text
    ),
    Final = Table.RemoveColumns(ComMotivo, {"leitura"})
in
    Final
