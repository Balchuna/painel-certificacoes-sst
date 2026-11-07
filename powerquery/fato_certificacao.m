// Carregar no modelo: sim
// Uma linha por emissão de treinamento ou ASO: as datas da aba Controle (já despivotadas) mais
// as emissões anteriores da aba Historico. Uma célula ou linha com data inválida não entra.
// Além das quatro colunas da versão limpa, traz três calculadas aqui, para as medidas ficarem simples:
//   data_vencimento  emissão + validade em meses (vazia quando o treinamento não vence). Date.AddMonths
//                    para no último dia do mês quando o dia não existe: 31/01 + 1 mês = 28/02 (ou 29/02),
//                    como DATAM no Excel e EDATE no Power BI.
//   vigente          verdadeiro na emissão mais recente do funcionário naquele treinamento; é a que vale.
//   regra            SIM, NÃO ou CONDICIONAL: a regra da função do funcionário para esse treinamento.
let
    Codigos = dim_treinamento[codigo],
    DoControle = Table.SelectRows(stg_DatasControle, each [data] <> null and List.Contains(Codigos, [coluna])),
    Controle = Table.AddColumn(
        Table.RenameColumns(
            Table.SelectColumns(DoControle, {"matricula", "coluna", "data"}),
            {{"coluna", "treinamento"}, {"data", "data_emissao"}}
        ),
        "origem", each "Controle", type text
    ),
    DoHistorico = Table.SelectRows(stg_Historico, each [motivo] = null),
    Historico = Table.AddColumn(
        Table.RenameColumns(
            Table.SelectColumns(DoHistorico, {"matricula", "treinamento", "data"}),
            {{"data", "data_emissao"}}
        ),
        "origem", each "Historico", type text
    ),
    Emissoes = Table.TransformColumnTypes(
        Table.Combine({Controle, Historico}),
        {{"matricula", Int64.Type}, {"treinamento", type text}, {"data_emissao", type date}}
    ),

    // Vencimento: a validade vem de dim_treinamento.
    ComTreinamento = Table.NestedJoin(Emissoes, {"treinamento"}, dim_treinamento, {"codigo"}, "t", JoinKind.LeftOuter),
    ComValidade = Table.ExpandTableColumn(ComTreinamento, "t", {"validade_meses"}),
    ComVencimento = Table.AddColumn(
        ComValidade,
        "data_vencimento",
        each if [validade_meses] = null or [validade_meses] = 0 then null
            else Date.AddMonths([data_emissao], [validade_meses]),
        type nullable date
    ),

    // Vigente: a emissão mais recente de cada funcionário em cada treinamento.
    Ultimas = Table.Group(
        ComVencimento, {"matricula", "treinamento"}, {{"ultima_emissao", each List.Max([data_emissao]), type date}}
    ),
    ComUltimas = Table.NestedJoin(
        ComVencimento, {"matricula", "treinamento"}, Ultimas, {"matricula", "treinamento"}, "u", JoinKind.LeftOuter
    ),
    ComUltima = Table.ExpandTableColumn(ComUltimas, "u", {"ultima_emissao"}),
    ComVigente = Table.AddColumn(ComUltima, "vigente", each [data_emissao] = [ultima_emissao], type logical),

    // Regra: a função vem do cadastro e a regra, da tabela de regras.
    ComFuncionario = Table.NestedJoin(ComVigente, {"matricula"}, dim_funcionario, {"matricula"}, "f", JoinKind.LeftOuter),
    ComFuncao = Table.ExpandTableColumn(ComFuncionario, "f", {"funcao"}),
    ComRegras = Table.NestedJoin(
        ComFuncao, {"funcao", "treinamento"}, regra_funcao_treinamento, {"funcao", "treinamento"}, "r", JoinKind.LeftOuter
    ),
    ComRegra = Table.ExpandTableColumn(ComRegras, "r", {"regra"}),

    Colunas = Table.SelectColumns(
        ComRegra, {"matricula", "treinamento", "data_emissao", "origem", "data_vencimento", "vigente", "regra"}
    ),
    Tipada = Table.TransformColumnTypes(
        Colunas,
        {
            {"matricula", Int64.Type}, {"treinamento", type text}, {"data_emissao", type date},
            {"origem", type text}, {"data_vencimento", type date}, {"vigente", type logical}, {"regra", type text}
        }
    ),
    Ordenada = Table.Sort(Tipada, {"matricula", "treinamento", "data_emissao", "origem"})
in
    Ordenada
