// Carregar no modelo: não (é uma função)
// Lê uma célula de data. Aceita data do Excel ou texto no formato dd/mm/aaaa, com ou sem espaços
// sobrando. Célula vazia (ou só com espaços) vira null.
// A data do Excel pode chegar de dois jeitos: como data ou como o número de série que o Excel
// guarda por baixo (46327 = 1º/11/2026). O leitor do Power Query entrega número quando não
// reconhece o formato da célula como data, o que acontece com as planilhas geradas pelo projeto;
// por isso número também é lido como data. Ver docs/DECISOES.md.
// Qualquer outra coisa, inclusive uma data que não existe como 31/02/2025, dá o erro "Data inválida".
// Quem chama usa try para saber se a célula era inválida e registrar a rejeição.
(valor as any) as nullable date =>
let
    Invalida = () => error Error.Record("Data inválida", "Não é data do Excel nem dd/mm/aaaa", valor),
    Lida =
        if valor = null then
            null
        else if valor is datetime then
            DateTime.Date(valor)
        else if valor is date then
            valor
        else if valor is number then
            try DateTime.Date(DateTime.From(valor)) otherwise Invalida()
        else
            let
                Texto = fn_LimparTexto(valor),
                Partes = Text.Split(Texto, "/"),
                NoFormato =
                    List.Count(Partes) = 3
                        and List.Transform(Partes, Text.Length) = {2, 2, 4}
                        and Text.Remove(Text.Combine(Partes), {"0".."9"}) = "",
                Data =
                    if not NoFormato then
                        null
                    else
                        try #date(Number.From(Partes{2}), Number.From(Partes{1}), Number.From(Partes{0}))
                            otherwise null
            in
                if Texto = "" then null else if Data = null then Invalida() else Data
in
    Lida
