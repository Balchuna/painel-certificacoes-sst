// Carregar no modelo: não (é uma função)
// Lê a matrícula: depois de tirar os espaços, só pode ter dígitos.
// Se não for um número, a atualização para com um erro que diz a aba e a linha, como a limpeza em Python.
(valor as any, onde as text) as number =>
let
    Texto = fn_LimparTexto(valor),
    Valida = Texto <> "" and Text.Remove(Texto, {"0".."9"}) = ""
in
    if Valida then
        Number.From(Texto)
    else
        error Error.Record("Matrícula inválida", onde & ": a matrícula """ & Texto & """ não é um número", valor)
