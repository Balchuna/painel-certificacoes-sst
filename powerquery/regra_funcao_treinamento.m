// Carregar no modelo: sim
// A regra de cada função para cada treinamento: SIM (obrigatório), NÃO (não se aplica) ou
// CONDICIONAL (depende da atividade). A aba vem larga, uma coluna por treinamento; aqui ela é
// despivotada para uma linha por par função e treinamento.
// Maiúsculas e espaços não importam ("  sim " vale SIM). Qualquer outro valor, inclusive célula
// vazia, para a atualização com um erro que diz a linha e o treinamento.
let
    Aba = fn_LerAba("parametros.xlsx", "Regra_Funcao_Treinamento"),
    Codigos = dim_treinamento[codigo],
    ComFuncao = Table.AddColumn(Aba, "funcao", each fn_LimparTexto([#"Função"]), type text),
    SoRegras = Table.SelectColumns(ComFuncao, {"linha", "funcao"} & Codigos),
    // Célula vazia vira texto vazio antes de despivotar, para não sumir e cair na conferência abaixo.
    Limpas = Table.TransformColumns(
        SoRegras, List.Transform(Codigos, (codigo) => {codigo, each Text.Upper(fn_LimparTexto(_)), type text})
    ),
    Longa = Table.UnpivotOtherColumns(Limpas, {"linha", "funcao"}, "treinamento", "regra"),
    Invalidas = Table.SelectRows(Longa, each not List.Contains({"SIM", "NÃO", "CONDICIONAL"}, [regra])),
    Conferida =
        if Table.IsEmpty(Invalidas) then
            Longa
        else
            error Error.Record(
                "Regra inválida",
                "Regra_Funcao_Treinamento, linha " & Text.From(Invalidas{0}[linha]) & ", "
                    & Invalidas{0}[treinamento] & ": """ & Invalidas{0}[regra]
                    & """ não é SIM, NÃO nem CONDICIONAL"
            ),
    Final = Table.TransformColumnTypes(
        Table.SelectColumns(Conferida, {"funcao", "treinamento", "regra"}),
        {{"treinamento", type text}, {"regra", type text}}
    )
in
    Final
