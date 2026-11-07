// Carregar no modelo: sim (é a tabela que guarda as medidas)
// Uma tabela vazia, só para as medidas de dax/medidas.dax ficarem juntas num lugar do painel de
// campos, em vez de espalhadas pelas tabelas. A coluna "oculta" existe porque toda tabela precisa
// de uma; esconda-a no Power BI e a tabela passa a mostrar só as medidas.
let
    Medidas = #table(type table [oculta = text], {})
in
    Medidas
