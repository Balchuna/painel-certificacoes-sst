// Carregar no modelo: não (desmarque "Habilitar carga")
// Despivota as colunas de data da aba Controle: de uma coluna por treinamento (formato largo)
// para uma linha por célula preenchida (formato longo). Entram a admissão, o desligamento e
// os doze treinamentos, só das linhas que não são matrícula repetida.
// Cada célula é lida com fn_LerData. A que não é data válida fica com "invalida" = verdadeiro e
// data vazia: vira uma rejeição em qualidade_rejeicoes e não vira emissão.
let
    Colunas = {"Admissão", "Desligamento"} & dim_treinamento[codigo],
    Unicas = Table.SelectRows(stg_Controle, each not [duplicada]),
    SoDatas = Table.SelectColumns(Unicas, {"linha", "matricula"} & Colunas),
    // O despivotar deixa de fora as células vazias, que não são emissão nem erro.
    Longa = Table.UnpivotOtherColumns(SoDatas, {"linha", "matricula"}, "coluna", "valor"),
    Lida = Table.AddColumn(Longa, "leitura", each try fn_LerData([valor])),
    ComData = Table.AddColumn(
        Lida, "data", each if [leitura][HasError] then null else [leitura][Value], type nullable date
    ),
    ComInvalida = Table.AddColumn(ComData, "invalida", each [leitura][HasError], type logical),
    // A posição da coluna na planilha, para a tabela de qualidade sair na ordem da limpeza em Python.
    ComPosicao = Table.AddColumn(ComInvalida, "posicao", each List.PositionOf(Colunas, [coluna]), Int64.Type),
    Final = Table.RemoveColumns(ComPosicao, {"leitura"})
in
    Final
