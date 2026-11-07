// Carregar no modelo: sim
// Um dia por linha, de 1º de janeiro do primeiro ano com alguma emissão ou vencimento até
// 31 de dezembro do último. Liga em fato_certificacao[data_vencimento]: é o eixo do gráfico
// "vencimentos por mês". Marque como tabela de datas no Power BI (coluna "data").
//   mes_ano              rótulo curto, "nov/2026"; classifique por ano_mes para sair em ordem de data.
//   ano_mes              202611: número que ordena os meses.
//   meses_da_referencia  0 no mês da data de referência, 1 no seguinte, -1 no anterior. Filtrar
//                        de 0 a 11 mostra os próximos doze meses sem mexer no filtro quando a data muda.
let
    Referencia = parametro{0}[data_referencia],
    Datas = List.RemoveNulls(fato_certificacao[data_emissao] & fato_certificacao[data_vencimento] & {Referencia}),
    Inicio = #date(Date.Year(List.Min(Datas)), 1, 1),
    Fim = #date(Date.Year(List.Max(Datas)), 12, 31),
    Dias = List.Dates(Inicio, Duration.Days(Fim - Inicio) + 1, #duration(1, 0, 0, 0)),
    Base = Table.FromColumns({Dias}, type table [data = date]),
    Meses = {"jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"},
    ComAno = Table.AddColumn(Base, "ano", each Date.Year([data]), Int64.Type),
    ComMes = Table.AddColumn(ComAno, "mes", each Date.Month([data]), Int64.Type),
    ComMesAno = Table.AddColumn(ComMes, "mes_ano", each Meses{[mes] - 1} & "/" & Text.From([ano]), type text),
    ComAnoMes = Table.AddColumn(ComMesAno, "ano_mes", each [ano] * 100 + [mes], Int64.Type),
    ComDistancia = Table.AddColumn(
        ComAnoMes,
        "meses_da_referencia",
        each ([ano] - Date.Year(Referencia)) * 12 + [mes] - Date.Month(Referencia),
        Int64.Type
    )
in
    ComDistancia
