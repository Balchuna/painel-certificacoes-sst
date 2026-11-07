// Carregar no modelo: sim
// As equipes que aparecem no cadastro, uma por linha. Serve de filtro nas páginas do painel.
let
    Equipes = Table.Distinct(Table.SelectColumns(dim_funcionario, {"equipe"})),
    Ordenada = Table.Sort(Equipes, {"equipe"})
in
    Ordenada
