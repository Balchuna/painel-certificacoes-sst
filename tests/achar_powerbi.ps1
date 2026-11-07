# Acha a pasta bin do Power BI Desktop (Microsoft Store ou instalador). Para outra pasta,
# defina a variável de ambiente POWERBI_BIN. Usado por ler_modelo_tom.ps1 e motor_powerbi.ps1.
function Achar-Bin {
    if ($env:POWERBI_BIN) { return $env:POWERBI_BIN }
    $pacote = Get-AppxPackage -Name Microsoft.MicrosoftPowerBIDesktop -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($pacote) { return Join-Path $pacote.InstallLocation 'bin' }
    $instalador = Join-Path $env:ProgramFiles 'Microsoft Power BI Desktop\bin'
    if (Test-Path $instalador) { return $instalador }
    return $null
}
