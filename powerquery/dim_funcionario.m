// Carregar no modelo: sim
// Uma linha por matrícula, da aba Controle: a primeira ocorrência de cada matrícula.
// Os textos saem sem espaços sobrando. Admissão ou desligamento com data inválida fica vazio
// (e aparece em qualidade_rejeicoes).
// "funcionario" junta matrícula e nome ("7001 - Fulano"): é o rótulo das linhas da matriz farol,
// que assim não junta dois homônimos numa linha só.
let
    Unicas = Table.SelectRows(stg_Controle, each not [duplicada]),
    LerData = (valor) => try fn_LerData(valor) otherwise null,
    ComNome = Table.AddColumn(Unicas, "nome", each fn_LimparTexto([Nome]), type text),
    ComFuncao = Table.AddColumn(ComNome, "funcao", each fn_LimparTexto([#"Função"]), type text),
    ComEquipe = Table.AddColumn(ComFuncao, "equipe", each fn_LimparTexto([Equipe]), type text),
    ComAdmissao = Table.AddColumn(ComEquipe, "admissao", each LerData([#"Admissão"]), type nullable date),
    ComSituacao = Table.AddColumn(ComAdmissao, "situacao", each fn_LimparTexto([#"Situação"]), type text),
    ComDesligamento = Table.AddColumn(ComSituacao, "desligamento", each LerData([Desligamento]), type nullable date),
    ComRotulo = Table.AddColumn(
        ComDesligamento, "funcionario", each Text.From([matricula]) & " - " & [nome], type text
    ),
    Colunas = Table.SelectColumns(
        ComRotulo,
        {"matricula", "nome", "funcao", "equipe", "admissao", "situacao", "desligamento", "funcionario"}
    ),
    Ordenada = Table.Sort(Colunas, {"matricula"})
in
    Ordenada
