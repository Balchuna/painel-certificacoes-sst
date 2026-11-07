// Carregar no modelo: não (é uma função)
// Lê uma aba de uma das planilhas da pasta de entrada e devolve:
//   - o cabeçalho limpo (sem espaços sobrando), como nome das colunas;
//   - a coluna "linha", com o número da linha no Excel, para a tabela de qualidade dizer onde está o problema;
//   - só as linhas que têm pelo menos uma célula preenchida.
// As células chegam como estão na planilha: data do Excel, número ou texto. Quem chama converte.
(arquivo as text, aba as text) as table =>
let
    Conteudo =
        try Arquivos{[Name = arquivo]}[Content]
            otherwise error Error.Record("Arquivo não encontrado", "Não achei " & arquivo & " na pasta " & PastaEntrada),
    Pasta = Excel.Workbook(Conteudo, null, true),
    Dados =
        try Pasta{[Item = aba, Kind = "Sheet"]}[Data]
            otherwise error Error.Record("Aba não encontrada", arquivo & " não tem a aba " & aba),
    Colunas = Table.ColumnNames(Dados),
    // A primeira linha da aba é o cabeçalho. Coluna sem título fica com o nome que o Power Query deu.
    Titulos = List.Transform(Record.FieldValues(Dados{0}), fn_LimparTexto),
    NovosNomes = List.Transform(List.Positions(Colunas), each if Titulos{_} = "" then Colunas{_} else Titulos{_}),
    // A linha 1 do Excel é o cabeçalho; a primeira linha de dados é a 2.
    Corpo = Table.AddIndexColumn(Table.Skip(Dados, 1), "linha", 2, 1, Int64.Type),
    Preenchidas = Table.SelectRows(Corpo, each List.NonNullCount(Record.FieldValues(Record.SelectFields(_, Colunas))) > 0),
    Renomeada = Table.RenameColumns(Preenchidas, List.Zip({Colunas, NovosNomes}))
in
    Renomeada
