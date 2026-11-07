"""O pacote do Power BI, rodado dentro do Excel e dentro do Power BI Desktop.

O Power Query de powerquery/ tem de chegar à mesma versão limpa da limpeza em
Python, e as medidas de dax/medidas.dax, ao mesmo gabarito do SQL, item por item.
Roda em dois cenários: a entrada versionada e uma entrada variada (outra semente,
outra data de referência, outras janelas, células feitas para pegar as bordas
da limpeza e itens vencendo em cada fronteira das janelas).

Os mesmos testes rodam em dois motores:
- excel: o Excel monta o pacote por automação (modelo_excel.py). Precisa de Windows
  com Excel e pywin32. Leva uns 20 minutos, porque cada consulta DAX custa uns
  13 segundos de ida e volta. Para deixar de fora: python -m pytest -m "not excel".
- desktop: o Power BI Desktop abre o projeto gerado por scripts/montar_pbip.py e
  atualiza (modelo_powerbi.py). Abre uma janela na tela, por isso só roda com
  python -m pytest --desktop. Leva uns 2 minutos.
Sem o programa de um motor, os testes daquele motor são pulados.
"""
from __future__ import annotations

import csv
import json
import sqlite3
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from pathlib import Path

import openpyxl
import pytest

from apoio import (
    CONTROLE,
    ENTRADA_VERSIONADA,
    LIMPA_VERSIONADA,
    PARAMETROS,
    RAIZ,
    SCRIPT_GABARITO,
    SCRIPT_LIMPEZA,
    TREINAMENTOS,
    gerar_ok,
    ler_csv,
    ler_regras,
    ler_validades,
    limpar_texto,
    rodar_ok,
    somar_meses,
)
from modelo_excel import ModeloExcel, data_excel, excel_instalado, relacionamentos
from modelo_powerbi import ModeloPowerBI, desktop_instalado

TABELAS_LIMPAS = [
    "dim_funcionario",
    "dim_funcao",
    "dim_treinamento",
    "regra_funcao_treinamento",
    "fato_certificacao",
    "parametro",
    "qualidade_rejeicoes",
]
DATAS = {"admissao", "desligamento", "data_emissao", "data_referencia", "data_vencimento", "data"}
PERCENTUAIS = {"pct_conformidade", "pct_pendencia", "pct_do_total"}
TEM_DATA = {"Vencido", "Válido"}  # mais os "Vence em ..."
ROTULO_SEM_DATA = {
    "Sem registro": "falta",
    "Sem vencimento": "sem venc.",
    "Condicional sem registro": "cond.",
    "Não aplicável": "n/a",
}


@dataclass
class Cenario:
    nome: str
    limpa: Path
    gabarito: Path
    banco: sqlite3.Connection
    modelo: ModeloExcel | ModeloPowerBI

    def sql(self, consulta: str) -> list[dict]:
        return [dict(linha) for linha in self.banco.execute(consulta)]

    def esperado(self, consulta: str) -> list[dict]:
        return ler_csv(self.gabarito / f"{consulta}.csv")


REFERENCIA_VARIADA = date(2026, 6, 1)
JANELAS_VARIADAS = (15, 45, 75)


def emissao_que_vence_em(vencimento: date, meses: int) -> date:
    """A emissão que, somados os meses como na DATAM, vence nesse dia."""
    candidata = somar_meses(vencimento, -meses) - timedelta(days=3)
    for _ in range(7):
        if somar_meses(candidata, meses) == vencimento:
            return candidata
        candidata += timedelta(days=1)
    raise AssertionError(f"nenhuma emissão vence em {vencimento} com {meses} meses")


def plantar_fronteiras(controle, coluna, historico, entrada: Path) -> None:
    """Um item obrigatório que vence em cada fronteira: ontem, hoje, o último dia de
    cada janela e o dia seguinte. É onde um < trocado por <= muda a conta."""
    validades, regras = ler_validades(entrada), ler_regras(entrada)
    com_historico = {
        (str(matricula).strip(), limpar_texto(treinamento))
        for matricula, treinamento, _ in historico.iter_rows(min_row=2, values_only=True)
    }
    matriculas = [controle.cell(l, coluna["Matrícula"]).value for l in range(2, controle.max_row + 1)]
    j1, j2, j3 = JANELAS_VARIADAS
    linha = 14  # as linhas de cima já têm os outros defeitos
    for dias in (-1, 0, j1, j1 + 1, j2, j2 + 1, j3, j3 + 1):
        while True:
            matricula = controle.cell(linha, coluna["Matrícula"]).value
            funcao = limpar_texto(controle.cell(linha, coluna["Função"]).value)
            livres = [
                t for t in TREINAMENTOS
                if regras[funcao][t] == "SIM" and validades[t] > 0
                and (str(matricula), t) not in com_historico
            ]
            ativo = limpar_texto(controle.cell(linha, coluna["Situação"]).value) == "Ativo"
            if ativo and livres and matriculas.count(matricula) == 1:
                break
            linha += 1
        vencimento = REFERENCIA_VARIADA + timedelta(days=dias)
        emissao = emissao_que_vence_em(vencimento, validades[livres[0]])
        controle.cell(linha, coluna[livres[0]]).value = datetime.combine(emissao, time())
        linha += 1


def montar_variado(entrada: Path) -> None:
    """Outra semente e outra data, mais células que a geração padrão não tem."""
    gerar_ok(entrada, "--semente", "7", "--data-referencia", REFERENCIA_VARIADA.isoformat())

    livro = openpyxl.load_workbook(entrada / CONTROLE)
    controle = livro["Controle"]
    coluna = {celula.value: celula.column for celula in controle[1]}

    def celula(linha, titulo):
        return controle.cell(linha, coluna[titulo])

    plantar_fronteiras(controle, coluna, livro["Historico"], entrada)
    celula(5, "Matrícula").value = f"  {celula(5, 'Matrícula').value} "
    celula(5, "Nome").value = celula(5, "Nome").value.replace(" ", "\t", 1)
    celula(6, "Equipe").value = celula(6, "Equipe").value.replace(" ", "\xa0")
    celula(7, "Desligamento").value = "31/04/2025"  # abril tem 30 dias
    celula(8, "ASO").value = datetime(2026, 1, 15, 14, 30)  # data com hora
    celula(9, "NR35").value = " 05/03/2026  "
    celula(10, "NR06").value = "2026-03-05"  # texto fora do formato dd/mm/aaaa
    celula(11, "NR18").value = "   "  # só espaços conta como vazio
    controle.insert_rows(13)  # uma linha vazia no meio

    historico = livro["Historico"]
    titulos = [c.value for c in historico[1]]
    matricula = celula(3, "Matrícula").value
    for valores in (
        {"Matrícula": matricula, "Treinamento": "NR35", "Data de emissão": "30/02/2024"},
        {"Matrícula": matricula, "Treinamento": "NR06", "Data de emissão": None},
        {"Matrícula": matricula, "Treinamento": " NR18 ", "Data de emissão": " 10/10/2019 "},
        {"Matrícula": f" {matricula}", "Treinamento": "NR01", "Data de emissão": "  "},
    ):
        historico.append([valores[titulo] for titulo in titulos])
    livro.save(entrada / CONTROLE)

    livro = openpyxl.load_workbook(entrada / PARAMETROS)
    for linha in livro["Alertas"].iter_rows(min_row=2):
        janela = dict(zip(
            ("Janela de alerta 1 (dias)", "Janela de alerta 2 (dias)", "Janela de alerta 3 (dias)"),
            JANELAS_VARIADAS,
        )).get(linha[0].value)
        if janela:
            linha[1].value = janela
    regras = livro["Regra_Funcao_Treinamento"]
    regras.cell(2, 3).value = f" {regras.cell(2, 3).value.lower()} "
    livro.save(entrada / PARAMETROS)


def abrir_modelo(motor: str, entrada: Path, pasta: Path) -> ModeloExcel | ModeloPowerBI:
    if motor == "excel":
        pytest.importorskip("win32com.client", reason="precisa do pywin32")
        if not excel_instalado():
            pytest.skip("precisa do Excel instalado")
        return ModeloExcel(entrada)
    if not desktop_instalado():
        pytest.skip("precisa do Power BI Desktop instalado")
    return ModeloPowerBI(entrada, pasta / "desktop")


@pytest.fixture(scope="module", params=[
    pytest.param(("padrao", "excel"), id="padrao-excel", marks=pytest.mark.excel),
    pytest.param(("variado", "excel"), id="variado-excel", marks=pytest.mark.excel),
    pytest.param(("padrao", "desktop"), id="padrao-desktop", marks=pytest.mark.desktop),
    pytest.param(("variado", "desktop"), id="variado-desktop", marks=pytest.mark.desktop),
])
def cenario(request, tmp_path_factory):
    nome, motor = request.param
    pasta = tmp_path_factory.mktemp(f"{nome}-{motor}")
    if nome == "padrao":
        entrada, limpa = ENTRADA_VERSIONADA, LIMPA_VERSIONADA
    else:
        entrada, limpa = pasta / "entrada", pasta / "limpa"
        montar_variado(entrada)
        rodar_ok(SCRIPT_LIMPEZA, "--entrada", entrada, "--saida", limpa)
    rodar_ok(SCRIPT_GABARITO, "--limpa", limpa, "--banco", pasta / "painel.sqlite",
             "--gabarito", pasta / "gabarito")
    banco = sqlite3.connect(pasta / "painel.sqlite")
    banco.row_factory = sqlite3.Row
    try:
        modelo = abrir_modelo(motor, entrada, pasta)
    except BaseException:
        banco.close()
        raise
    try:
        yield Cenario(nome, limpa, pasta / "gabarito", banco, modelo)
    finally:
        modelo.fechar()
        banco.close()


def como_texto(coluna, valor) -> str:
    """O valor do modelo escrito como no CSV."""
    if valor is None or valor == "":
        return ""
    if coluna in DATAS:
        return data_excel(valor).isoformat()
    if isinstance(valor, float) and valor.is_integer():
        return str(int(valor))
    return str(valor)


def cabecalho(caminho: Path) -> list[str]:
    with open(caminho, encoding="utf-8", newline="") as arquivo:
        return next(csv.reader(arquivo))


def conferir(obtido: list[dict], esperado: list[dict]) -> None:
    assert len(obtido) == len(esperado)
    for numero, (linha, certa) in enumerate(zip(obtido, esperado)):
        for coluna, valor in certa.items():
            if coluna in PERCENTUAIS:
                assert abs(linha[coluna] - float(valor)) <= 0.0501, (numero, coluna, linha, certa)
            else:
                assert como_texto(coluna, linha[coluna]) == valor, (numero, coluna, linha, certa)


# --- Power Query -----------------------------------------------------------------


@pytest.mark.parametrize("tabela", TABELAS_LIMPAS)
def test_power_query_chega_a_versao_limpa(cenario, tabela):
    colunas = cabecalho(cenario.limpa / f"{tabela}.csv")
    esperado = sorted(tuple(linha[c] for c in colunas) for linha in ler_csv(cenario.limpa / f"{tabela}.csv"))
    obtido = sorted(
        tuple(como_texto(c, linha[c]) for c in colunas)
        for linha in cenario.modelo.consultar(f"EVALUATE '{tabela}'")
    )
    assert obtido == esperado


def test_vencimento_de_cada_emissao_soma_os_meses_como_o_excel(cenario):
    validade = {t["codigo"]: int(t["validade_meses"]) for t in ler_csv(cenario.limpa / "dim_treinamento.csv")}
    linhas = cenario.modelo.consultar("EVALUATE 'fato_certificacao'")
    assert linhas
    for linha in linhas:
        emissao, meses = data_excel(linha["data_emissao"]), validade[linha["treinamento"]]
        esperado = None if meses == 0 else somar_meses(emissao, meses)
        assert data_excel(linha["data_vencimento"]) == esperado, linha


def test_vigente_e_a_emissao_mais_recente(cenario):
    esperado = sorted(
        (str(l["matricula"]), l["treinamento"], l["data_emissao"], l["data_vencimento"] or "")
        for l in cenario.sql("SELECT * FROM vw_registro_vigente")
    )
    obtido = sorted(
        tuple(como_texto(c, l[c]) for c in ("matricula", "treinamento", "data_emissao", "data_vencimento"))
        for l in cenario.modelo.consultar("EVALUATE FILTER('fato_certificacao', fato_certificacao[vigente])")
    )
    assert obtido == esperado


def test_cada_emissao_traz_a_regra_da_funcao(cenario):
    esperado = sorted(
        (str(l["matricula"]), l["treinamento"], l["data_emissao"], l["regra"])
        for l in cenario.sql(
            "SELECT f.matricula, f.treinamento, f.data_emissao, r.regra"
            " FROM fato_certificacao AS f"
            " JOIN dim_funcionario AS d USING (matricula)"
            " JOIN regra_funcao_treinamento AS r"
            "   ON r.funcao = d.funcao AND r.treinamento = f.treinamento"
        )
    )
    obtido = sorted(
        tuple(como_texto(c, l[c]) for c in ("matricula", "treinamento", "data_emissao", "regra"))
        for l in cenario.modelo.consultar("EVALUATE 'fato_certificacao'")
    )
    assert obtido == esperado


def test_equipes(cenario):
    esperado = sorted({l["equipe"] for l in ler_csv(cenario.limpa / "dim_funcionario.csv")})
    obtido = sorted(l["equipe"] for l in cenario.modelo.consultar("EVALUATE 'dim_equipe'"))
    assert obtido == esperado


def test_calendario_sem_buracos_cobre_todas_as_datas(cenario):
    dias = cenario.modelo.consultar("EVALUATE 'dim_calendario'")
    datas = sorted(data_excel(l["data"]) for l in dias)
    assert [(b - a).days for a, b in zip(datas, datas[1:])] == [1] * (len(datas) - 1)
    assert (datas[0].month, datas[0].day, datas[-1].month, datas[-1].day) == (1, 1, 12, 31)

    fato = cenario.modelo.consultar("EVALUATE 'fato_certificacao'")
    usadas = {data_excel(l[c]) for l in fato for c in ("data_emissao", "data_vencimento")} - {None}
    assert datas[0] <= min(usadas) and max(usadas) <= datas[-1]

    referencia = data_excel(cenario.modelo.consultar("EVALUATE 'parametro'")[0]["data_referencia"])
    assert datas[0] <= referencia <= datas[-1]
    for l in dias:
        data = data_excel(l["data"])
        assert l["ano_mes"] == data.year * 100 + data.month
        assert l["meses_da_referencia"] == (data.year - referencia.year) * 12 + data.month - referencia.month


def test_relacionamentos_de_modelo_md_estao_ativos(cenario):
    ligacoes = cenario.modelo.ligacoes()
    assert sorted((muitos, um) for muitos, um, _ in ligacoes) == sorted(relacionamentos())
    assert len(ligacoes) > 0 and all(ativa for _, _, ativa in ligacoes)


# --- Medidas DAX contra o gabarito do SQL ----------------------------------------


def test_visao_geral(cenario):
    obtido = cenario.modelo.medir("""
EVALUATE ROW (
    "data_referencia", [Data de Referência],
    "funcionarios_ativos", [Funcionários Ativos] + 0,
    "funcionarios_irregulares", [Funcionários Irregulares] + 0,
    "itens_obrigatorios", [Itens Obrigatórios] + 0,
    "itens_validos", [Itens Válidos] + 0,
    "pct_conformidade", [% Conformidade] * 100,
    "pendentes_obrigatorios", [Pendentes Obrigatórios] + 0,
    "obrigatorios_sem_registro", [Obrigatórios Sem Registro] + 0,
    "obrigatorios_vencidos", [Obrigatórios Vencidos] + 0,
    "itens_vencidos", [Vencidos] + 0
)""")
    conferir(obtido, cenario.esperado("01_visao_geral"))


def test_vencimentos_nas_tres_janelas(cenario):
    linhas = []
    for janela, medida in (("janela_1", "Vencem em 30 dias"), ("janela_2", "Vencem em 60 dias"),
                           ("janela_3", "Vencem em 90 dias")):
        linhas += cenario.modelo.medir(f"""
EVALUATE ROW (
    "janela_dias", MAX ( parametro[{janela}] ),
    "itens", [{medida}] + 0,
    "itens_obrigatorios", CALCULATE ( [{medida}], KEEPFILTERS ( fato_certificacao[regra] = "SIM" ) ) + 0,
    "funcionarios", COUNTROWS ( FILTER ( VALUES ( dim_funcionario[matricula] ), [{medida}] > 0 ) ) + 0
)""")
    conferir(linhas, cenario.esperado("03_vencimentos_30_60_90"))


def test_pendencias_por_funcao(cenario):
    obtido = cenario.modelo.medir("""
EVALUATE
FILTER (
    ADDCOLUMNS (
        VALUES ( dim_funcao[funcao] ),
        "funcionarios_ativos", [Funcionários Ativos] + 0,
        "funcionarios_irregulares", [Funcionários Irregulares] + 0,
        "itens_obrigatorios", [Itens Obrigatórios] + 0,
        "itens_validos", [Itens Válidos] + 0,
        "pendentes", [Pendentes Obrigatórios] + 0,
        "sem_registro", [Obrigatórios Sem Registro] + 0,
        "vencidos", [Obrigatórios Vencidos] + 0,
        "pct_conformidade", [% Conformidade] * 100,
        "pct_pendencia", [% Pendência] * 100,
        "pct_do_total", DIVIDE ( [Pendentes Obrigatórios], CALCULATE ( [Pendentes Obrigatórios], ALL ( dim_funcao ) ) ) * 100
    ),
    [funcionarios_ativos] > 0
)""")
    obtido.sort(key=lambda l: (-l["pendentes"] / l["itens_obrigatorios"], l["funcao"]))
    conferir(obtido, cenario.esperado("05_pendencias_por_funcao"))


def test_pendencias_por_treinamento(cenario):
    obtido = cenario.modelo.medir("""
EVALUATE
FILTER (
    ADDCOLUMNS (
        SUMMARIZE ( dim_treinamento, dim_treinamento[codigo], dim_treinamento[nome] ),
        "itens_obrigatorios", [Itens Obrigatórios] + 0,
        "itens_validos", [Itens Válidos] + 0,
        "pendentes", [Pendentes Obrigatórios] + 0,
        "sem_registro", [Obrigatórios Sem Registro] + 0,
        "vencidos", [Obrigatórios Vencidos] + 0,
        "pct_conformidade", [% Conformidade] * 100,
        "pct_pendencia", [% Pendência] * 100,
        "pct_do_total", DIVIDE ( [Pendentes Obrigatórios], CALCULATE ( [Pendentes Obrigatórios], ALL ( dim_treinamento ) ) ) * 100
    ),
    [itens_obrigatorios] > 0
)""")
    for linha in obtido:
        linha["treinamento"], linha["treinamento_nome"] = linha.pop("codigo"), linha.pop("nome")
    obtido.sort(key=lambda l: (-l["pendentes"] / l["itens_obrigatorios"], l["treinamento"]))
    conferir(obtido, cenario.esperado("06_pendencias_por_treinamento"))


def test_irregulares_hoje(cenario):
    obtido = cenario.modelo.medir("""
EVALUATE
FILTER (
    ADDCOLUMNS (
        SUMMARIZE ( dim_funcionario, dim_funcionario[matricula], dim_funcionario[nome],
                    dim_funcionario[funcao], dim_funcionario[equipe] ),
        "pendencias", [Pendentes Obrigatórios] + 0,
        "sem_registro", [Obrigatórios Sem Registro] + 0,
        "vencidos", [Obrigatórios Vencidos] + 0,
        "treinamentos", CONCATENATEX (
            FILTER ( VALUES ( dim_treinamento[codigo] ), [Pendentes Obrigatórios] > 0 ),
            dim_treinamento[codigo], ", ", dim_treinamento[codigo], ASC )
    ),
    [pendencias] > 0
)""")
    obtido.sort(key=lambda l: (-l["pendencias"], l["matricula"]))
    conferir(obtido, cenario.esperado("02_irregulares_hoje"))


ITENS = """
EVALUATE
FILTER (
    ADDCOLUMNS (
        CROSSJOIN ( VALUES ( dim_funcionario[matricula] ), VALUES ( dim_treinamento[codigo] ) ),
        "nome", CALCULATE ( VALUES ( dim_funcionario[nome] ) ),
        "funcao", CALCULATE ( VALUES ( dim_funcionario[funcao] ) ),
        "equipe", CALCULATE ( VALUES ( dim_funcionario[equipe] ) ),
        "regra", [Regra do Item],
        "data_emissao", [Emissão do Item],
        "data_vencimento", [Vencimento do Item],
        "dias_para_vencer", [Dias para Vencer],
        "status", [Status Farol],
        "rotulo", [Rótulo Farol],
        "cor", [Cor Farol],
        "na_agenda", [Na Agenda]
    ),
    NOT ISBLANK ( [status] )
)"""


@pytest.fixture(scope="module")
def itens(cenario):
    linhas = cenario.modelo.medir(ITENS)
    for linha in linhas:
        linha["treinamento"] = linha.pop("codigo")
    return linhas


def test_agenda_de_reciclagem(cenario, itens):
    agenda = [l for l in itens if l["na_agenda"] == 1]
    agenda.sort(key=lambda l: (l["data_vencimento"], l["matricula"], l["treinamento"]))
    conferir(agenda, cenario.esperado("04_agenda_reciclagem"))


def test_variado_tem_obrigatorio_em_cada_fronteira(cenario):
    """Sem itens nas fronteiras, trocar < por <= numa medida passaria despercebido."""
    if cenario.nome != "variado":
        pytest.skip("as fronteiras são plantadas só no cenário variado")
    j1, j2, j3 = cenario.sql("SELECT janela_1, janela_2, janela_3 FROM parametro")[0].values()
    dias = {
        l["dias_para_vencer"]
        for l in cenario.sql("SELECT dias_para_vencer FROM vw_status_item WHERE regra = 'SIM'")
    }
    assert {-1, 0, j1, j1 + 1, j2, j2 + 1, j3, j3 + 1} <= dias


def test_status_de_cada_item(cenario, itens):
    colunas = ("matricula", "treinamento", "regra", "data_emissao", "data_vencimento",
               "dias_para_vencer", "status")
    esperado = sorted(
        tuple("" if l[c] is None else str(l[c]) for c in colunas)
        for l in cenario.sql("SELECT * FROM vw_status_item")
    )
    obtido = sorted(tuple(como_texto(c, l[c]) for c in colunas) for l in itens)
    assert obtido == esperado


def test_cor_e_rotulo_seguem_o_status(cenario, itens):
    tema = json.loads((RAIZ / "tema" / "tema.json").read_text(encoding="utf-8"))
    cores_do_tema = {cor.upper() for cor in tema["dataColors"]}
    cor_do_status = {}
    for linha in itens:
        status = linha["status"]
        assert cor_do_status.setdefault(status, linha["cor"]) == linha["cor"], status
        if status in ROTULO_SEM_DATA:
            assert linha["rotulo"] == ROTULO_SEM_DATA[status], linha
        else:
            assert status in TEM_DATA or status.startswith("Vence em "), status
            assert linha["rotulo"] == data_excel(linha["data_vencimento"]).strftime("%d/%m/%y"), linha
    assert len(set(cor_do_status.values())) == len(cor_do_status)
    assert {cor.upper() for cor in cor_do_status.values()} <= cores_do_tema
    if cenario.nome == "padrao":
        assert len(cor_do_status) == 9


def test_vencimentos_por_mes(cenario):
    esperado = {
        l["ano_mes"]: l["itens"]
        for l in cenario.sql(
            "SELECT CAST(strftime('%Y%m', data_vencimento) AS INTEGER) AS ano_mes, COUNT(*) AS itens"
            " FROM vw_status_item WHERE regra <> 'NÃO' AND data_vencimento IS NOT NULL GROUP BY 1"
        )
    }
    obtido = cenario.modelo.medir(
        'EVALUATE SUMMARIZECOLUMNS ( dim_calendario[ano_mes], "itens", [Itens com Vencimento] )'
    )
    assert {int(l["ano_mes"]): int(l["itens"]) for l in obtido} == esperado


def test_linhas_rejeitadas(cenario):
    obtido = cenario.modelo.medir('EVALUATE ROW ( "linhas", [Linhas Rejeitadas] + 0 )')
    assert obtido[0]["linhas"] == len(ler_csv(cenario.limpa / "qualidade_rejeicoes.csv"))


# --- Mensagens de erro -----------------------------------------------------------


def textos_do_erro(valor) -> list[str]:
    """Os textos de um erro. O do Excel vem em tuplas dentro de tuplas; o do Desktop, na saída de erro."""
    if isinstance(valor, str):
        return [valor]
    if isinstance(valor, BaseException):
        return textos_do_erro(valor.args) + textos_do_erro(getattr(valor, "stderr", None))
    if isinstance(valor, tuple):
        return [texto for parte in valor for texto in textos_do_erro(parte)]
    return []


@pytest.mark.parametrize("motor", [
    pytest.param("excel", marks=pytest.mark.excel),
    pytest.param("desktop", marks=pytest.mark.desktop),
])
def test_pasta_de_entrada_errada_aparece_na_mensagem(motor, tmp_path):
    # Com PastaEntrada apontando para uma pasta que não existe, o Power BI dizia que a
    # planilha "não tem a aba". A mensagem tem de falar da pasta, que é onde está o erro.
    pasta = tmp_path / "pasta que não existe"
    with pytest.raises(Exception) as erro:
        abrir_modelo(motor, pasta, tmp_path).fechar()
    texto = " ".join(textos_do_erro(erro.value))
    assert "não tem a aba" not in texto
    assert str(pasta) in texto
