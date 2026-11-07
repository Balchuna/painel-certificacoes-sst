"""Abre o projeto do Power BI no Power BI Desktop, atualiza e responde consultas DAX.

Faz com o Power BI Desktop o que modelo_excel.py faz com o Excel. Gera o projeto com
scripts/montar_pbip.py apontando para a pasta de entrada, abre o projeto numa janela do
Power BI Desktop, pede a atualização ao motor que o Desktop roda por dentro e responde
consultas DAX. A conversa com o motor fica em motor_powerbi.ps1, que usa as bibliotecas
do próprio Power BI Desktop.

As medidas são as do modelo do projeto, sem o bloco DEFINE de dax/medidas.dax: o que se
confere é o projeto como o Desktop o carrega. As datas voltam como número de série do
Excel, para os testes lerem os dois motores do mesmo jeito.

Abre uma janela na tela, por isso só roda com a opção --desktop do pytest. No fim, fecha
a janela sem salvar.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

from modelo_excel import nome_da_coluna

RAIZ = Path(__file__).resolve().parents[1]
GERADOR = RAIZ / "scripts" / "montar_pbip.py"
MOTOR = RAIZ / "tests" / "motor_powerbi.ps1"
POWERSHELL = ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass"]
ESPERA = 300  # segundos para o Desktop abrir o projeto e carregar o modelo


def executavel_do_desktop() -> Path | None:
    """O Power BI Desktop da Microsoft Store abre pelo atalho de WindowsApps; o do instalador, pelo exe."""
    candidatos = [
        Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "WindowsApps" / "PBIDesktopStore.exe",
        Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Microsoft Power BI Desktop" / "bin" / "PBIDesktop.exe",
    ]
    return next((caminho for caminho in candidatos if caminho.exists()), None)


def desktop_instalado() -> bool:
    return sys.platform == "win32" and executavel_do_desktop() is not None


def _powershell(*argumentos: str) -> str:
    return subprocess.run(
        [*POWERSHELL, *argumentos], capture_output=True, text=True, encoding="utf-8", check=True,
    ).stdout


def _motores() -> dict[int, int]:
    """{processo do motor (msmdsrv): processo do Power BI Desktop que o abriu}."""
    saida = _powershell(
        "-Command",
        "Get-CimInstance Win32_Process | Where-Object Name -eq 'msmdsrv.exe'"
        " | ForEach-Object { '{0} {1}' -f $_.ProcessId, $_.ParentProcessId }",
    )
    return {int(motor): int(pai) for motor, pai in (linha.split() for linha in saida.splitlines() if linha.strip())}


def _porta(motor: int) -> int | None:
    saida = _powershell(
        "-Command",
        f"try {{ Get-NetTCPConnection -OwningProcess {motor} -State Listen -ErrorAction Stop"
        " | Select-Object -First 1 -ExpandProperty LocalPort } catch {}",
    ).strip()
    return int(saida) if saida else None


class ModeloPowerBI:
    def __init__(self, pasta_entrada: Path, pasta_trabalho: Path):
        self.pasta = Path(pasta_trabalho)
        self.desktop = None
        self.motor = None
        self.porta = None
        try:
            self._abrir(Path(pasta_entrada))
        except BaseException:
            self.fechar()
            raise

    def _abrir(self, entrada: Path) -> None:
        projeto = self.pasta / "projeto"
        subprocess.run(
            [sys.executable, str(GERADOR), "--saida", str(projeto), "--pasta-entrada", str(entrada)],
            capture_output=True, text=True, encoding="utf-8", check=True,
        )
        antes = _motores()
        subprocess.Popen([str(executavel_do_desktop()), str(projeto / "PainelSST.pbip")])

        prazo = time.monotonic() + ESPERA
        while self.porta is None:
            if time.monotonic() > prazo:
                raise TimeoutError("o Power BI Desktop não abriu o motor a tempo")
            time.sleep(3)
            novos = {m: p for m, p in _motores().items() if m not in antes}
            if novos:
                self.motor, self.desktop = next(iter(novos.items()))
                self.porta = _porta(self.motor)

        while not self._modelo()["tabelas"]:
            if time.monotonic() > prazo:
                raise TimeoutError("o Power BI Desktop não carregou o modelo a tempo")
            time.sleep(3)
        self._chamar("atualizar")

    def _chamar(self, acao: str, *argumentos: str) -> object:
        saida = _powershell("-File", str(MOTOR), "-Porta", str(self.porta), "-Acao", acao, *argumentos)
        return json.loads(saida)

    def _modelo(self) -> dict:
        return self._chamar("modelo")

    def tabelas(self) -> list[str]:
        return self._modelo()["tabelas"]

    def ligacoes(self) -> list[tuple[tuple[str, str], tuple[str, str], bool]]:
        """[((tabela, coluna) do lado muitos, (tabela, coluna) do lado um, ativa?)]."""
        return [((a, b), (c, d), ativa) for a, b, c, d, ativa in self._modelo()["ligacoes"]]

    def consultar(self, dax: str) -> list[dict]:
        """Roda uma consulta DAX e devolve as linhas como dicionários."""
        arquivo = self.pasta / "consulta.dax"
        arquivo.write_text(dax, encoding="utf-8")
        linhas = self._chamar("dax", "-Arquivo", str(arquivo))
        return [{nome_da_coluna(coluna): valor for coluna, valor in linha.items()} for linha in linhas]

    def medir(self, consulta: str) -> list[dict]:
        """Roda uma consulta EVALUATE com as medidas que estão no modelo do projeto."""
        return self.consultar(consulta)

    def fechar(self) -> None:
        processos = [p for p in (self.desktop, self.motor) if p]
        self.desktop = self.motor = None
        if processos:
            ids = ",".join(map(str, processos))
            _powershell("-Command", f"foreach ($p in {ids}) {{ try {{ Stop-Process -Id $p -Force -ErrorAction Stop }} catch {{}} }}")
