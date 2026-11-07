// Carregar no modelo: sim
// Os treinamentos e a validade de cada um, da aba Treinamentos de parametros.xlsx.
// validade_meses = 0 quer dizer que o treinamento não vence (como a carteira).
// "ordem" é a posição na planilha: serve para a matriz farol mostrar as colunas na ordem de costume
// em vez da ordem alfabética (em "Classificar por coluna", no Power BI).
let
    Aba = fn_LerAba("parametros.xlsx", "Treinamentos"),
    ComCodigo = Table.AddColumn(Aba, "codigo", each fn_LimparTexto([#"Código"]), type text),
    ComNome = Table.AddColumn(ComCodigo, "nome", each fn_LimparTexto([Treinamento]), type text),
    ComValidade = Table.AddColumn(
        ComNome, "validade_meses", each Int64.From(Number.From([#"Validade (meses)"])), Int64.Type
    ),
    Colunas = Table.SelectColumns(ComValidade, {"codigo", "nome", "validade_meses"}),
    ComOrdem = Table.AddIndexColumn(Colunas, "ordem", 1, 1, Int64.Type)
in
    ComOrdem
