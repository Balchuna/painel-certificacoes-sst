# Conversa com o motor de um Power BI Desktop aberto (o Analysis Services que ele roda por dentro)
# usando as bibliotecas do próprio Power BI Desktop. Usado por tests/modelo_powerbi.py.
#   -Acao modelo     escreve as tabelas e as relações do modelo carregado, em JSON
#   -Acao atualizar  atualiza todas as tabelas (o mesmo que o botão Atualizar)
#   -Acao dax        roda a consulta DAX do arquivo -Arquivo e escreve as linhas em JSON;
#                    as datas saem como número de série do Excel (dias desde 30/12/1899)
param(
    [Parameter(Mandatory = $true)][int]$Porta,
    [Parameter(Mandatory = $true)][ValidateSet('modelo', 'atualizar', 'dax')][string]$Acao,
    [string]$Arquivo
)
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding $false

. (Join-Path $PSScriptRoot 'achar_powerbi.ps1')
$bin = Achar-Bin
[void][Reflection.Assembly]::LoadFrom((Join-Path $bin 'Microsoft.PowerBI.Tabular.dll'))
[void][Reflection.Assembly]::LoadFrom((Join-Path $bin 'Microsoft.PowerBI.AdomdClient.dll'))

$servidor = New-Object Microsoft.AnalysisServices.Tabular.Server
$servidor.Connect("Data Source=localhost:$Porta")
try {
    if ($servidor.Databases.Count -eq 0) {
        if ($Acao -eq 'modelo') { Write-Output '{"tabelas": [], "ligacoes": []}'; exit 0 }
        throw 'O Power BI Desktop ainda não carregou o modelo.'
    }
    $banco = $servidor.Databases[0]
    $modelo = $banco.Model

    if ($Acao -eq 'modelo') {
        $ligacoes = @(foreach ($r in $modelo.Relationships) {
            , @($r.FromTable.Name, $r.FromColumn.Name, $r.ToTable.Name, $r.ToColumn.Name, $r.IsActive)
        })
        ConvertTo-Json -Compress -Depth 4 -InputObject ([ordered]@{
            tabelas  = @($modelo.Tables | ForEach-Object { $_.Name })
            ligacoes = $ligacoes
        })
    }
    elseif ($Acao -eq 'atualizar') {
        $modelo.RequestRefresh([Microsoft.AnalysisServices.Tabular.RefreshType]::Full)
        [void]$modelo.SaveChanges()
        Write-Output '{"atualizado": true}'
    }
    else {
        $conexao = New-Object Microsoft.AnalysisServices.AdomdClient.AdomdConnection(
            "Data Source=localhost:$Porta;Catalog=$($banco.ID)")
        $conexao.Open()
        try {
            $comando = $conexao.CreateCommand()
            $comando.CommandText = [IO.File]::ReadAllText($Arquivo, [Text.Encoding]::UTF8)
            $leitor = $comando.ExecuteReader()
            $linhas = New-Object System.Collections.ArrayList
            while ($leitor.Read()) {
                $linha = [ordered]@{}
                for ($i = 0; $i -lt $leitor.FieldCount; $i++) {
                    $valor = $leitor.GetValue($i)
                    if ($valor -is [DBNull]) { $valor = $null }
                    elseif ($valor -is [datetime]) { $valor = $valor.ToOADate() }
                    elseif ($valor -is [decimal]) { $valor = [double]$valor }
                    $linha[$leitor.GetName($i)] = $valor
                }
                [void]$linhas.Add($linha)
            }
            $leitor.Close()
            ConvertTo-Json -Compress -Depth 4 -InputObject @($linhas)
        }
        finally { $conexao.Close() }
    }
}
finally { $servidor.Disconnect() }
