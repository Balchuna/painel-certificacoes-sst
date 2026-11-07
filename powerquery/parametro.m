// Carregar no modelo: sim
// A data de referência e as três janelas de alerta (em dias), da aba Alertas de parametros.xlsx.
// É uma tabela de uma linha só. As medidas leem daqui: mudar a data ou as janelas na planilha e
// atualizar o painel muda todos os números, sem mexer em nenhuma fórmula.
let
    Aba = fn_LerAba("parametros.xlsx", "Alertas"),
    Valores = Record.FromList(Aba[Valor], List.Transform(Aba[#"Parâmetro"], fn_LimparTexto)),
    Pegar = (rotulo as text) =>
        if Record.HasFields(Valores, rotulo) then
            Record.Field(Valores, rotulo)
        else
            error Error.Record("Parâmetro não encontrado", "A aba Alertas não tem """ & rotulo & """"),
    Linha = {
        fn_LerData(Pegar("Data de referência")),
        Int64.From(Number.From(Pegar("Janela de alerta 1 (dias)"))),
        Int64.From(Number.From(Pegar("Janela de alerta 2 (dias)"))),
        Int64.From(Number.From(Pegar("Janela de alerta 3 (dias)")))
    },
    Tabela = #table({"data_referencia", "janela_1", "janela_2", "janela_3"}, {Linha}),
    Tipada = Table.TransformColumnTypes(
        Tabela,
        {{"data_referencia", type date}, {"janela_1", Int64.Type}, {"janela_2", Int64.Type}, {"janela_3", Int64.Type}}
    )
in
    Tipada
