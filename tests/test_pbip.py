"""O projeto do Power BI em powerbi/ é o que scripts/montar_pbip.py gera a partir do pacote.

O Power BI Desktop abre a pasta powerbi/ como projeto (PBIP): o modelo fica em TMDL e o
relatório em PBIR, tudo em texto. Estes testes conferem que:
- os arquivos versionados são exatamente os que o gerador produz agora;
- o modelo é o do pacote: as consultas de powerquery/, as medidas de dax/medidas.dax e as
  relações de docs/MODELO.md. Quem lê o modelo é a biblioteca do próprio Power BI Desktop;
  sem ele instalado, esses testes são pulados;
- cada visual usa tabelas, colunas e medidas que existem no modelo.

Os números não são conferidos aqui: quem confere é test_powerbi.py, no Excel e, com a
opção --desktop, no próprio Power BI Desktop, que abre este projeto e atualiza.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys

import pytest

from modelo_excel import MODELO, RAIZ, bloco_define, consultas, medidas, relacionamentos

POWERBI = RAIZ / "powerbi"
GERADOR = RAIZ / "scripts" / "montar_pbip.py"
LER_TOM = RAIZ / "tests" / "ler_modelo_tom.ps1"
MODELO_PBIP = POWERBI / "PainelSST.SemanticModel" / "definition"
RELATORIO = POWERBI / "PainelSST.Report" / "definition"
TEMA = RAIZ / "tema" / "tema.json"

PAGINAS = ["Visão geral", "Matriz farol", "Agenda de reciclagem", "Qualidade dos dados"]
CARTOES_DA_VISAO_GERAL = {
    "Data de Referência",
    "Funcionários Ativos",
    "Funcionários Irregulares",
    "% Conformidade",
    "Pendentes Obrigatórios",
    "Vencidos",
    "Vencem em 30 dias",
    "Vencem em 60 dias",
    "Vencem em 90 dias",
}
# Os tipos que docs/MODELO.md usa, e o nome deles no modelo do Power BI.
TIPOS = {"número inteiro": "Int64", "texto": "String", "data": "DateTime", "verdadeiro/falso": "Boolean"}
# Arquivos que o Power BI Desktop cria ao abrir o projeto e que não vão para o repositório.
LOCAIS = re.compile(r"(^|/)\.pbi/")


def gerar(saida, *argumentos):
    return subprocess.run(
        [sys.executable, str(GERADOR), "--saida", str(saida), *argumentos],
        capture_output=True, text=True, encoding="utf-8", check=True,
    )


def arquivos(pasta) -> dict[str, bytes]:
    return {
        caminho.relative_to(pasta).as_posix(): caminho.read_bytes()
        for caminho in sorted(pasta.rglob("*"))
        if caminho.is_file() and not LOCAIS.search(caminho.relative_to(pasta).as_posix())
    }


def compacto(texto: str) -> str:
    """O texto sem diferença de espaços e quebras de linha."""
    return " ".join(texto.split())


def corpo_m(texto: str) -> str:
    """A consulta sem o comentário do começo, que no modelo vira a descrição."""
    return re.sub(r"\A(?://[^\n]*\n)+", "", texto.replace("\r\n", "\n"))


def corpos_das_medidas() -> dict[str, str]:
    partes = re.split(r"^\s*MEASURE\s+Medidas\[([^\]]+)\]\s*=", bloco_define(), flags=re.M)
    corpos = {}
    for nome, corpo in zip(partes[1::2], partes[2::2]):
        linhas = corpo.rstrip().splitlines()
        while linhas and (not linhas[-1].strip() or linhas[-1].strip().startswith("//")):
            linhas.pop()
        corpos[nome] = compacto("\n".join(linhas))
    return corpos


# ---------------------------------------------------------------------------------------------
# O gerador


@pytest.fixture(scope="module")
def gerado(tmp_path_factory):
    saida = tmp_path_factory.mktemp("pbip")
    gerar(saida)
    return saida


def test_projeto_versionado_e_o_que_o_gerador_produz(gerado):
    versionado, novo = arquivos(POWERBI), arquivos(gerado)
    assert sorted(versionado) == sorted(novo)
    diferentes = [nome for nome in novo if versionado[nome] != novo[nome]]
    assert not diferentes, "rode python scripts/montar_pbip.py"


def test_gerador_e_deterministico(gerado, tmp_path):
    gerar(tmp_path)
    assert arquivos(tmp_path) == arquivos(gerado)


def test_pasta_de_entrada_versionada_e_um_lugar_reservado():
    texto = (MODELO_PBIP / "expressions.tmdl").read_text(encoding="utf-8")
    assert '"C:\\caminho\\do\\projeto\\data\\entrada" meta' in texto


def test_gerador_aceita_outra_pasta_de_entrada(tmp_path):
    gerar(tmp_path, "--pasta-entrada", r"E:\dados\entrada")
    texto = (tmp_path / "PainelSST.SemanticModel" / "definition" / "expressions.tmdl").read_text(encoding="utf-8")
    assert '"E:\\dados\\entrada" meta' in texto
    assert "caminho\\do\\projeto" not in texto


def test_projeto_nao_traz_caminho_do_computador_de_ninguem():
    for nome, conteudo in arquivos(POWERBI).items():
        assert not re.search(rb"[A-Za-z]:(\\){1,2}Users(\\){1,2}", conteudo), nome


# ---------------------------------------------------------------------------------------------
# O modelo, lido pela biblioteca do Power BI Desktop


@pytest.fixture(scope="module")
def tom():
    if sys.platform != "win32":
        pytest.skip("a biblioteca do Power BI Desktop só existe no Windows")
    resultado = subprocess.run(
        ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(LER_TOM), "-Pasta", str(MODELO_PBIP)],
        capture_output=True, text=True, encoding="utf-8",
    )
    assert resultado.returncode == 0, resultado.stderr
    dados = json.loads(resultado.stdout)
    if dados.get("ausente"):
        pytest.skip("Power BI Desktop não instalado")
    return dados


def tabelas_tom(tom) -> dict[str, dict]:
    return {tabela["name"]: tabela for tabela in tom["tables"]}


@pytest.mark.powerbi
def test_tabelas_sao_as_consultas_carregadas(tom):
    pacote = consultas()
    tabelas = tabelas_tom(tom)
    assert set(tabelas) == {nome for nome, (_, carrega) in pacote.items() if carrega}
    for nome, tabela in tabelas.items():
        (particao,) = tabela["partitions"]
        assert particao["kind"] == "M" and particao["mode"] == "Import", nome
        assert compacto(particao["expression"]) == compacto(corpo_m(pacote[nome][0])), nome


@pytest.mark.powerbi
def test_consultas_que_nao_carregam_ficam_como_expressoes(tom):
    pacote = consultas()
    expressoes = {expressao["name"]: expressao for expressao in tom["expressions"]}
    assert set(expressoes) == {nome for nome, (_, carrega) in pacote.items() if not carrega}
    for nome, expressao in expressoes.items():
        assert compacto(expressao["expression"]) == compacto(corpo_m(pacote[nome][0])), nome
    assert "IsParameterQuery = true" in expressoes["PastaEntrada"]["expression"]


@pytest.mark.powerbi
def test_ordem_das_consultas_e_a_do_passo_a_passo(tom):
    ordem = json.loads(tom["annotations"]["PBI_QueryOrder"])
    assert sorted(ordem) == sorted(consultas())
    texto = (RAIZ / "docs" / "MONTAGEM.md").read_text(encoding="utf-8")
    secao = re.search(r"^### 3\.2 .*?(?=^### )", texto, re.M | re.S).group(0)
    assert ordem == re.findall(r"^\|\s*\d+\s*\|\s*`(\w+)`", secao, re.M)


@pytest.mark.powerbi
def test_medidas_sao_as_do_arquivo_dax(tom):
    lidas = {medida["name"]: medida for medida in tabelas_tom(tom)["Medidas"]["measures"]}
    assert list(lidas) == medidas()
    corpos = corpos_das_medidas()
    for nome, medida in lidas.items():
        assert compacto(medida["expression"]) == corpos[nome], nome
    assert lidas["% Conformidade"]["formatString"] == "0.0%"
    assert lidas["Data de Referência"]["formatString"] == "dd/MM/yyyy"
    assert lidas["Funcionários Ativos"]["formatString"] == "0"
    # O comentário logo acima da medida, no arquivo DAX, vira a descrição que aparece no Power BI.
    descricao = "Itens obrigatórios que têm pelo menos uma emissão (vencida ou não)."
    assert lidas["Obrigatórios com Registro"]["description"] == descricao


@pytest.mark.powerbi
def test_relacoes_sao_as_de_modelo_md(tom):
    lidas = {(relacao["from"], relacao["to"]) for relacao in tom["relationships"]}
    esperadas = {(f"{a}[{b}]", f"{c}[{d}]") for (a, b), (c, d) in relacionamentos()}
    assert lidas == esperadas
    for relacao in tom["relationships"]:
        assert relacao["isActive"], relacao
        assert relacao["crossFilteringBehavior"] == "OneDirection", relacao
        assert (relacao["fromCardinality"], relacao["toCardinality"]) == ("Many", "One"), relacao


@pytest.mark.powerbi
def test_colunas_tem_os_tipos_de_modelo_md(tom):
    texto = MODELO.read_text(encoding="utf-8")
    secoes = dict(re.findall(r"^###\s+`(\w+)`\n(.*?)(?=^###|^## |\Z)", texto, re.M | re.S))
    for nome, tabela in tabelas_tom(tom).items():
        documentadas = set(re.findall(r"`(\w+)`", secoes[nome]))
        tipos = {coluna: tipo for coluna, tipo in re.findall(r"^\|\s*`(\w+)`\*?\s*\|\s*([^|]+?)\s*\|", secoes[nome], re.M)}
        for coluna in tabela["columns"]:
            assert coluna["name"] in documentadas, (nome, coluna["name"])
            assert coluna["sourceColumn"] == coluna["name"], (nome, coluna["name"])
            assert coluna["summarizeBy"] == "None", (nome, coluna["name"])
            if coluna["name"] in tipos:
                assert coluna["dataType"] == TIPOS[tipos[coluna["name"]]], (nome, coluna["name"])


@pytest.mark.powerbi
def test_ajustes_do_passo_a_passo(tom):
    tabelas = tabelas_tom(tom)

    def coluna(tabela, nome):
        return next(c for c in tabelas[tabela]["columns"] if c["name"] == nome)

    assert tom["annotations"]["__PBI_TimeIntelligenceEnabled"] == "0"
    assert coluna("dim_treinamento", "codigo")["sortByColumn"] == "ordem"
    assert coluna("dim_calendario", "mes_ano")["sortByColumn"] == "ano_mes"
    assert tabelas["dim_calendario"]["dataCategory"] == "Time"
    assert coluna("dim_calendario", "data")["isKey"]
    ocultas = {(t, c["name"]) for t, tabela in tabelas.items() for c in tabela["columns"] if c["isHidden"]}
    assert ocultas == {("Medidas", "oculta"), ("dim_treinamento", "ordem"), ("dim_calendario", "ano_mes")}


# ---------------------------------------------------------------------------------------------
# O relatório


def visuais():
    for caminho in sorted(RELATORIO.glob("pages/*/visuals/*/visual.json")):
        yield caminho.parts[-4], json.loads(caminho.read_text(encoding="utf-8"))


def campos_usados(objeto, apelidos=None):
    """(Column ou Measure, tabela, nome) de cada campo citado no visual, filtros inclusive."""
    apelidos = dict(apelidos or {})
    if isinstance(objeto, dict):
        for origem in objeto.get("From", []):
            apelidos[origem["Name"]] = origem["Entity"]
        for tipo in ("Column", "Measure"):
            campo = objeto.get(tipo)
            if isinstance(campo, dict) and "Property" in campo:
                referencia = campo["Expression"]["SourceRef"]
                yield tipo, referencia.get("Entity") or apelidos[referencia["Source"]], campo["Property"]
        for valor in objeto.values():
            yield from campos_usados(valor, apelidos)
    elif isinstance(objeto, list):
        for valor in objeto:
            yield from campos_usados(valor, apelidos)


def campos_do_modelo() -> set[tuple[str, str, str]]:
    campos = set()
    for caminho in (MODELO_PBIP / "tables").glob("*.tmdl"):
        texto = caminho.read_text(encoding="utf-8")
        tabela = re.search(r"^table (\S+)", texto, re.M).group(1)
        for tipo, nome in re.findall(r"^\t(column|measure) ('(?:[^']|'')*'|[^\s=]+)", texto, re.M):
            if nome.startswith("'"):
                nome = nome[1:-1].replace("''", "'")
            campos.add(("Column" if tipo == "column" else "Measure", tabela, nome))
    return campos


def projecoes(visual, papel):
    estado = visual["visual"].get("query", {}).get("queryState", {})
    return [p["field"] for p in estado.get(papel, {}).get("projections", [])]


def nome_do_campo(campo):
    return next(iter(campo.values()))["Property"]


def test_paginas_na_ordem_do_passo_a_passo():
    ordem = json.loads((RELATORIO / "pages" / "pages.json").read_text(encoding="utf-8"))["pageOrder"]
    nomes = [
        json.loads((RELATORIO / "pages" / pagina / "page.json").read_text(encoding="utf-8"))["displayName"]
        for pagina in ordem
    ]
    assert nomes == PAGINAS


def test_visuais_usam_campos_que_existem():
    modelo = campos_do_modelo()
    for pagina, visual in visuais():
        for campo in campos_usados(visual):
            assert campo in modelo, (pagina, visual["name"], campo)


def test_cartoes_da_visao_geral():
    cartoes = {
        nome_do_campo(campo)
        for pagina, visual in visuais()
        if pagina == "visao_geral" and visual["visual"]["visualType"] == "card"
        for campo in projecoes(visual, "Values")
    }
    assert cartoes == CARTOES_DA_VISAO_GERAL


def test_matriz_farol_pinta_cada_celula_com_a_cor_farol():
    (matriz,) = [v for p, v in visuais() if p == "matriz_farol" and v["visual"]["visualType"] == "pivotTable"]
    assert [nome_do_campo(c) for c in projecoes(matriz, "Rows")] == ["funcionario"]
    assert [nome_do_campo(c) for c in projecoes(matriz, "Columns")] == ["codigo"]
    assert [nome_do_campo(c) for c in projecoes(matriz, "Values")] == ["Rótulo Farol"]
    (fundo,) = matriz["visual"]["objects"]["values"]
    cor = fundo["properties"]["backColor"]["solid"]["color"]["expr"]["Measure"]["Property"]
    assert cor == "Cor Farol"


def test_agenda_mostra_so_o_que_vence_na_maior_janela():
    (tabela,) = [v for p, v in visuais() if p == "agenda" and v["visual"]["visualType"] == "tableEx"]
    filtros = {nome_do_campo(f["field"]): f for f in tabela["filterConfig"]["filters"]}
    condicao = filtros["Na Agenda"]["filter"]["Where"][0]["Condition"]["Comparison"]
    assert condicao["ComparisonKind"] == 0 and condicao["Right"]["Literal"]["Value"] == "1L"
    (ordem,) = tabela["visual"]["query"]["sortDefinition"]["sort"]
    assert nome_do_campo(ordem["field"]) == "Vencimento do Item" and ordem["direction"] == "Ascending"


def test_relatorio_usa_o_tema_do_pacote():
    copia = POWERBI / "PainelSST.Report" / "StaticResources" / "RegisteredResources" / "tema.json"
    assert json.loads(copia.read_text(encoding="utf-8")) == json.loads(TEMA.read_text(encoding="utf-8"))
    relatorio = json.loads((RELATORIO / "report.json").read_text(encoding="utf-8"))
    assert relatorio["themeCollection"]["customTheme"]["name"] == "tema.json"
