// Carregar no modelo: sim
// As funções que têm regra na aba Regra_Funcao_Treinamento de parametros.xlsx.
let
    Aba = fn_LerAba("parametros.xlsx", "Regra_Funcao_Treinamento"),
    ComFuncao = Table.AddColumn(Aba, "funcao", each fn_LimparTexto([#"Função"]), type text),
    Final = Table.SelectColumns(ComFuncao, {"funcao"})
in
    Final
