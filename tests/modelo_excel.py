"""Monta o pacote do Power BI dentro do Excel, para testar o M e o DAX.

O Power BI Desktop não roda pela linha de comando, mas o Excel traz os mesmos dois
motores: o Power Query, que roda os arquivos de powerquery/, e o modelo de dados
(Power Pivot), que calcula as medidas de dax/medidas.dax. Este módulo abre um Excel
escondido, cria as consultas, carrega no modelo as que o Power BI carrega, liga as
tabelas como docs/MODELO.md manda e responde consultas DAX.

Tudo o que ele usa vem dos arquivos do pacote: se o passo a passo estiver errado,
o teste cai.
"""
from __future__ import annotations

import gc
import re
from datetime import date, timedelta
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
POWERQUERY = RAIZ / "powerquery"
MEDIDAS = RAIZ / "dax" / "medidas.dax"
MODELO = RAIZ / "docs" / "MODELO.md"

CARREGAR = re.compile(r"// Carregar no modelo: (sim|não)")
# Uma linha da tabela de relacionamentos de MODELO.md: | `muitos[coluna]` | `um[coluna]` | ...
RELACAO = re.compile(r"^\|\s*`(\w+)\[(\w+)\]`\s*\|\s*`(\w+)\[(\w+)\]`\s*\|", re.M)
MEDIDA = re.compile(r"^\s*MEASURE\s+Medidas\[([^\]]+)\]\s*=", re.M)

XL_SRC_MODEL = 4
XL_YES = 1
XL_CMD_DAX = 8
XL_CMD_TABLE_COLLECTION = 6


def consultas() -> dict[str, tuple[str, bool]]:
    """{nome da consulta: (fórmula M, carrega no modelo?)}, lidos de powerquery/."""
    resultado = {}
    for arquivo in sorted(POWERQUERY.glob("*.m")):
        texto = arquivo.read_text(encoding="utf-8")
        marca = CARREGAR.match(texto)
        if not marca:
            raise ValueError(f"{arquivo.name} não começa dizendo se carrega no modelo")
        resultado[arquivo.stem] = (texto, marca.group(1) == "sim")
    return resultado


def relacionamentos() -> list[tuple[tuple[str, str], tuple[str, str]]]:
    """[((tabela, coluna) do lado muitos, (tabela, coluna) do lado um)], de docs/MODELO.md."""
    texto = MODELO.read_text(encoding="utf-8")
    return [((a, b), (c, d)) for a, b, c, d in RELACAO.findall(texto)]


def bloco_define() -> str:
    """O bloco DEFINE de dax/medidas.dax, sem a consulta de conferência do fim."""
    texto = MEDIDAS.read_text(encoding="utf-8")
    inicio = re.search(r"^DEFINE\b", texto, re.M)
    fim = re.search(r"^EVALUATE\b", texto, re.M)
    if not inicio or not fim:
        raise ValueError("dax/medidas.dax precisa de uma linha DEFINE e de uma linha EVALUATE")
    return texto[inicio.start():fim.start()]


def medidas() -> list[str]:
    return MEDIDA.findall(bloco_define())


def excel_instalado() -> bool:
    try:
        import winreg
    except ImportError:  # fora do Windows
        return False
    try:
        winreg.CloseKey(winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, "Excel.Application\\CLSID"))
        return True
    except OSError:
        return False


def data_excel(valor) -> date | None:
    """O Excel devolve datas como número de dias desde 30/12/1899."""
    if valor is None:
        return None
    return date(1899, 12, 30) + timedelta(days=int(valor))


def nome_da_coluna(cabecalho: str) -> str:
    """O resultado de EVALUATE 'tabela' vem como tabela[coluna]; fica só a coluna."""
    casamento = re.fullmatch(r".*\[(.+)\]", str(cabecalho))
    return casamento.group(1) if casamento else str(cabecalho)


class ModeloExcel:
    def __init__(self, pasta_entrada: Path):
        import pythoncom
        import win32com.client

        pythoncom.CoInitialize()
        self.excel = win32com.client.DispatchEx("Excel.Application")
        self.excel.Visible = False
        self.excel.DisplayAlerts = False
        self.livro = None
        self._tabela = None
        try:
            self._montar(Path(pasta_entrada))
        except BaseException:
            self.fechar()
            raise

    def _montar(self, pasta: Path) -> None:
        self.livro = self.excel.Workbooks.Add()
        # Sem níveis de privacidade, como num Power BI que lê de uma fonte só.
        self.livro.Queries.FastCombine = True
        pacote = consultas()
        for nome, (formula, _) in pacote.items():
            if nome == "PastaEntrada":
                formula = re.sub(r'^"[^"]*"', lambda _: f'"{pasta}"', formula, count=1, flags=re.M)
            self.livro.Queries.Add(nome, formula)
        for nome, (_, carregar) in pacote.items():
            if carregar:
                self._carregar(nome)

        modelo = self.livro.Model
        for (muitos, coluna_muitos), (um, coluna_um) in relacionamentos():
            modelo.ModelRelationships.Add(
                modelo.ModelTables(muitos).ModelTableColumns(coluna_muitos),
                modelo.ModelTables(um).ModelTableColumns(coluna_um),
            )

        planilha = self.livro.Worksheets(1)
        conexao = modelo.CreateModelWorkbookConnection("parametro")
        self._tabela = planilha.ListObjects.Add(XL_SRC_MODEL, conexao, None, XL_YES, planilha.Range("A1"))
        self._tabela.TableObject.WorkbookConnection.OLEDBConnection.CommandType = XL_CMD_DAX

    def _carregar(self, nome: str) -> None:
        # O mesmo que "Carregar para > Adicionar ao Modelo de Dados" no Excel.
        self.livro.Connections.Add2(
            f"Consulta - {nome}",
            f"Conexão com a consulta '{nome}' na pasta de trabalho.",
            "OLEDB;Provider=Microsoft.Mashup.OleDb.1;Data Source=$Workbook$;"
            f'Location={nome};Extended Properties=""',
            f'"{nome}"',
            XL_CMD_TABLE_COLLECTION,
            True,
            False,
        )

    def tabelas(self) -> list[str]:
        return [tabela.Name for tabela in self.livro.Model.ModelTables]

    def ligacoes(self) -> list[tuple[tuple[str, str], tuple[str, str], bool]]:
        """[((tabela, coluna) do lado muitos, (tabela, coluna) do lado um, ativa?)]."""
        todas = self.livro.Model.ModelRelationships
        return [
            ((r.ForeignKeyTable.Name, r.ForeignKeyColumn.Name), (r.PrimaryKeyTable.Name, r.PrimaryKeyColumn.Name),
             bool(r.Active))
            for r in (todas.Item(i) for i in range(1, todas.Count + 1))
        ]

    def consultar(self, dax: str) -> list[dict]:
        """Roda uma consulta DAX e devolve as linhas como dicionários."""
        objeto = self._tabela.TableObject
        objeto.WorkbookConnection.OLEDBConnection.CommandText = dax
        objeto.Refresh()
        valores = self._tabela.Range.Value2
        cabecalho = [nome_da_coluna(titulo) for titulo in valores[0]]
        linhas = valores[1:] if self._tabela.ListRows.Count else ()
        return [dict(zip(cabecalho, linha)) for linha in linhas]

    def medir(self, consulta: str) -> list[dict]:
        """Roda uma consulta EVALUATE com as medidas de dax/medidas.dax definidas."""
        return self.consultar(bloco_define() + "\n" + consulta)

    def fechar(self) -> None:
        # Solta cada objeto do Excel antes de fechá-lo. Um objeto solto depois que o Excel
        # fechou dá o aviso 0x80010108 (objeto desconectado) no fim dos testes.
        # O gc.collect pega também os objetos presos em tracebacks de testes que falharam.
        self._tabela = None
        gc.collect()
        if self.livro is not None:
            livro, self.livro = self.livro, None
            livro.Close(False)
            del livro
        if self.excel is not None:
            excel, self.excel = self.excel, None
            excel.Quit()
            del excel
