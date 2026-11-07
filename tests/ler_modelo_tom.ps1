# Lê um modelo em TMDL com a biblioteca do próprio Power BI Desktop e escreve um resumo em JSON.
# Usado por tests/test_pbip.py. Sem o Power BI Desktop instalado, escreve {"ausente": true}.
# A pasta do Power BI é achada por achar_powerbi.ps1.
param([Parameter(Mandatory = $true)][string]$Pasta)
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding $false

. (Join-Path $PSScriptRoot 'achar_powerbi.ps1')

$bin = Achar-Bin
if (-not $bin -or -not (Test-Path (Join-Path $bin 'Microsoft.PowerBI.Tabular.dll'))) {
    Write-Output '{"ausente": true}'
    exit 0
}
[void][Reflection.Assembly]::LoadFrom((Join-Path $bin 'Microsoft.PowerBI.Tabular.dll'))

$banco = [Microsoft.AnalysisServices.Tabular.TmdlSerializer]::DeserializeDatabaseFromFolder($Pasta)
$modelo = $banco.Model

$anotacoes = [ordered]@{}
foreach ($a in $modelo.Annotations) { $anotacoes[$a.Name] = $a.Value }

$tabelas = @(foreach ($t in $modelo.Tables) {
    [ordered]@{
        name         = $t.Name
        isHidden     = $t.IsHidden
        dataCategory = $t.DataCategory
        columns      = @(foreach ($c in $t.Columns) {
            if ("$($c.Type)" -eq 'RowNumber') { continue }
            [ordered]@{
                name         = $c.Name
                dataType     = "$($c.DataType)"
                isHidden     = $c.IsHidden
                isKey        = $c.IsKey
                summarizeBy  = "$($c.SummarizeBy)"
                sortByColumn = $(if ($c.SortByColumn) { $c.SortByColumn.Name } else { $null })
                formatString = $c.FormatString
                sourceColumn = $c.SourceColumn
            }
        })
        measures     = @(foreach ($m in $t.Measures) {
            [ordered]@{
                name         = $m.Name
                expression   = $m.Expression
                formatString = $m.FormatString
                description  = $m.Description
                isHidden     = $m.IsHidden
            }
        })
        partitions   = @(foreach ($p in $t.Partitions) {
            [ordered]@{
                name       = $p.Name
                mode       = "$($p.Mode)"
                kind       = "$($p.SourceType)"
                expression = $p.Source.Expression
            }
        })
    }
})

$expressoes = @(foreach ($e in $modelo.Expressions) {
    [ordered]@{
        name        = $e.Name
        kind        = "$($e.Kind)"
        expression  = $e.Expression
        description = $e.Description
    }
})

$relacoes = @(foreach ($r in $modelo.Relationships) {
    [ordered]@{
        from                   = "$($r.FromTable.Name)[$($r.FromColumn.Name)]"
        to                     = "$($r.ToTable.Name)[$($r.ToColumn.Name)]"
        isActive               = $r.IsActive
        crossFilteringBehavior = "$($r.CrossFilteringBehavior)"
        fromCardinality        = "$($r.FromCardinality)"
        toCardinality          = "$($r.ToCardinality)"
    }
})

[ordered]@{
    compatibilityLevel = $banco.CompatibilityLevel
    culture            = $modelo.Culture
    annotations        = $anotacoes
    tables             = $tabelas
    expressions        = $expressoes
    relationships      = $relacoes
} | ConvertTo-Json -Depth 8
