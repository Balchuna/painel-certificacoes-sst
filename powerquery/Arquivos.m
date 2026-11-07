// Carregar no modelo: não (desmarque "Habilitar carga")
// A única fonte de dados do painel: os arquivos da pasta de entrada.
// As duas planilhas são lidas daqui. Com uma fonte só, o Power BI não pede níveis de privacidade
// para juntar dados das duas, e trocar de pasta é só mudar o parâmetro PastaEntrada.
let
    Fonte = Folder.Contents(PastaEntrada),
    Planilhas = Table.SelectRows(Fonte, each List.Contains({"controle_largo.xlsx", "parametros.xlsx"}, [Name])),
    Arquivos = Table.SelectColumns(Planilhas, {"Name", "Content"})
in
    Arquivos
