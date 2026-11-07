// Carregar no modelo: não (é uma função)
// Tira os espaços das pontas e junta espaços repetidos no meio: "  Equipe   Alfa " vira "Equipe Alfa".
// Faz o mesmo que " ".join(texto.split()) na limpeza em Python, inclusive com tabulação,
// quebra de linha e espaço não separável. Célula vazia vira texto vazio.
(valor as any) as text =>
let
    Texto = if valor = null then "" else Text.From(valor, "en-US"),
    // Os caracteres que o Python considera espaço em branco.
    Espacos = Text.Combine(
        List.Transform(
            {9, 10, 11, 12, 13, 28, 29, 30, 31, 32, 133, 160, 5760}
                & {8192..8202} & {8232, 8233, 8239, 8287, 12288},
            Character.FromNumber
        )
    ),
    Pedacos = Text.SplitAny(Texto, Espacos),
    Limpo = Text.Combine(List.Select(Pedacos, each _ <> ""), " ")
in
    Limpo
