"""Gera o projeto do Power BI (PBIP) a partir do pacote do painel.

Um projeto PBIP é uma pasta que o Power BI Desktop abre como um .pbix: o modelo fica em
TMDL e o relatório em PBIR, tudo em texto. Este script escreve essa pasta só com o que
já está no repositório:

- as consultas de powerquery/: as que carregam viram tabelas, as outras viram expressões;
- as medidas de dax/medidas.dax, com o comentário de cima de cada uma como descrição;
- as relações de docs/MODELO.md;
- o tema de tema/tema.json e a legenda do farol de docs/MONTAGEM.md;
- as quatro páginas de docs/MONTAGEM.md, com os ajustes de modelo do passo a passo.

Sem argumentos, regrava powerbi/ com o caminho de exemplo no parâmetro PastaEntrada. Para
abrir e atualizar no seu computador, gere uma cópia fora do repositório com o caminho de
verdade da pasta data/entrada (o Power Query não aceita caminho relativo):

    python scripts/montar_pbip.py --pasta-entrada "D:/painel-certificacoes-sst/data/entrada" --saida ../painel-local
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
import textwrap
import uuid
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
POWERQUERY = RAIZ / "powerquery"
MEDIDAS = RAIZ / "dax" / "medidas.dax"
MODELO = RAIZ / "docs" / "MODELO.md"
MONTAGEM = RAIZ / "docs" / "MONTAGEM.md"
TEMA = RAIZ / "tema" / "tema.json"
SAIDA_PADRAO = RAIZ / "powerbi"

NOME = "PainelSST"
CAMINHO_DE_EXEMPLO = r"C:\caminho\do\projeto\data\entrada"
# Gera sempre as mesmas identificações (lineageTag), para o projeto não mudar a cada execução.
ESPACO = uuid.uuid5(uuid.NAMESPACE_URL, "painel-certificacoes-sst")

ESQUEMAS = "https://developer.microsoft.com/json-schemas/fabric/"
VERSOES = {"report": "3.0.0", "page": "2.0.0", "visual": "2.4.0"}

# Colunas de cada tabela, na ordem de docs/MODELO.md. O tipo tem de ser o que a consulta entrega.
TEXTO, INTEIRO, DATA, LOGICO = "string", "int64", "dateTime", "boolean"
COLUNAS = {
    "dim_funcionario": [
        ("matricula", INTEIRO), ("nome", TEXTO), ("funcao", TEXTO), ("equipe", TEXTO),
        ("admissao", DATA), ("situacao", TEXTO), ("desligamento", DATA), ("funcionario", TEXTO),
    ],
    "dim_funcao": [("funcao", TEXTO)],
    "dim_equipe": [("equipe", TEXTO)],
    "dim_treinamento": [("codigo", TEXTO), ("nome", TEXTO), ("validade_meses", INTEIRO), ("ordem", INTEIRO)],
    "regra_funcao_treinamento": [("funcao", TEXTO), ("treinamento", TEXTO), ("regra", TEXTO)],
    "fato_certificacao": [
        ("matricula", INTEIRO), ("treinamento", TEXTO), ("data_emissao", DATA), ("origem", TEXTO),
        ("data_vencimento", DATA), ("vigente", LOGICO), ("regra", TEXTO),
    ],
    "dim_calendario": [
        ("data", DATA), ("ano", INTEIRO), ("mes", INTEIRO), ("mes_ano", TEXTO),
        ("ano_mes", INTEIRO), ("meses_da_referencia", INTEIRO),
    ],
    "parametro": [("data_referencia", DATA), ("janela_1", INTEIRO), ("janela_2", INTEIRO), ("janela_3", INTEIRO)],
    "qualidade_rejeicoes": [
        ("aba", TEXTO), ("linha", INTEIRO), ("matricula", INTEIRO), ("coluna", TEXTO),
        ("valor_original", TEXTO), ("motivo", TEXTO), ("acao", TEXTO),
    ],
    "Medidas": [("oculta", TEXTO)],
}
# Passo 4 de docs/MONTAGEM.md: ordem de classificação, colunas escondidas e tabela de datas.
CLASSIFICAR_POR = {("dim_treinamento", "codigo"): "ordem", ("dim_calendario", "mes_ano"): "ano_mes"}
ESCONDIDAS = {("Medidas", "oculta"), ("dim_treinamento", "ordem"), ("dim_calendario", "ano_mes")}
TABELA_DE_DATAS = ("dim_calendario", "data")
# Passo 5.4: formatos das medidas. As que não estão aqui são contagens, em número inteiro.
FORMATO_PERCENTUAL = {"% Conformidade", "% Pendência"}
FORMATO_DATA = {"Data de Referência", "Emissão do Item", "Vencimento do Item"}
SEM_FORMATO = {"Item Único", "Regra do Item", "Status Farol", "Cor Farol", "Rótulo Farol"}

CARREGAR = re.compile(r"// Carregar no modelo: (sim|não)")
RELACAO = re.compile(r"^\|\s*`(\w+)\[(\w+)\]`\s*\|\s*`(\w+)\[(\w+)\]`\s*\|", re.M)
ORDEM = re.compile(r"^\|\s*(\d+)\s*\|\s*`(\w+)`\s*\|\s*(sim|não)\s*\|", re.M)
FAROL = re.compile(r"^\|\s*(\d)\s*\|\s*([^|]+?)\s*\|\s*`(#[0-9A-Fa-f]{6})`", re.M)
NOME_SIMPLES = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


# ---------------------------------------------------------------------------------------------
# Leitura do pacote


def ler_ordem() -> dict[str, tuple[int, bool]]:
    """{consulta: (posição, carrega?)} da tabela do passo 3.2 de MONTAGEM.md."""
    texto = MONTAGEM.read_text(encoding="utf-8")
    secao = re.search(r"^### 3\.2 .*?(?=^### )", texto, re.M | re.S).group(0)
    return {nome: (int(numero), carrega == "sim") for numero, nome, carrega in ORDEM.findall(secao)}


def ler_consultas() -> list[dict]:
    """Cada consulta de powerquery/, na ordem do passo a passo."""
    ordem = ler_ordem()
    consultas = []
    for arquivo in POWERQUERY.glob("*.m"):
        texto = arquivo.read_text(encoding="utf-8").replace("\r\n", "\n")
        marca = CARREGAR.match(texto)
        if not marca:
            sys.exit(f"{arquivo.name} não começa dizendo se carrega no modelo")
        comentario = re.match(r"(?://[^\n]*\n)+", texto).group(0)
        descricao = [re.sub(r"^// ?", "", linha) for linha in comentario.splitlines()[1:]]
        carrega = marca.group(1) == "sim"
        if ordem.get(arquivo.stem, (0, carrega))[1] != carrega or arquivo.stem not in ordem:
            sys.exit(f"a tabela 3.2 de docs/MONTAGEM.md não traz {arquivo.stem} como o arquivo diz")
        consultas.append({
            "nome": arquivo.stem,
            "carrega": carrega,
            "descricao": "\n".join(descricao).strip(),
            "m": texto[len(comentario):].strip("\n"),
            "posicao": ordem[arquivo.stem][0],
        })
    return sorted(consultas, key=lambda consulta: consulta["posicao"])


def ler_medidas() -> list[dict]:
    """As medidas do bloco DEFINE de dax/medidas.dax, com o comentário logo acima como descrição."""
    texto = MEDIDAS.read_text(encoding="utf-8").replace("\r\n", "\n")
    inicio = re.search(r"^DEFINE\b", texto, re.M)
    fim = re.search(r"^EVALUATE\b", texto, re.M)
    linhas = texto[inicio.end():fim.start()].splitlines()
    medidas, comentario, atual = [], [], None
    for linha in linhas:
        cabecalho = re.match(r"^\s*MEASURE\s+Medidas\[([^\]]+)\]\s*=\s*(.*)$", linha)
        if cabecalho:
            atual = {"nome": cabecalho.group(1), "descricao": "\n".join(comentario), "corpo": [cabecalho.group(2)]}
            medidas.append(atual)
            comentario = []
        elif linha.strip().startswith("//"):
            conteudo = re.sub(r"^\s*// ?", "", linha)
            comentario = [] if set(conteudo.strip()) <= {"-"} else [*comentario, conteudo]
        elif not linha.strip():
            comentario = []
            if atual:
                atual["corpo"].append("")
        elif atual:
            atual["corpo"].append(linha)
    for medida in medidas:
        corpo = "\n".join(medida.pop("corpo")).strip("\n")
        medida["expressao"] = textwrap.dedent(corpo).strip()
        medida["descricao"] = medida["descricao"].strip()
    return medidas


def ler_relacoes() -> list[tuple[str, str, str, str]]:
    return RELACAO.findall(MODELO.read_text(encoding="utf-8"))


def ler_farol() -> list[tuple[str, str]]:
    """(situação, cor) dos nove códigos do farol, da tabela do passo 6 de MONTAGEM.md."""
    linhas = FAROL.findall(MONTAGEM.read_text(encoding="utf-8"))
    return [(situacao, cor.upper()) for _, situacao, cor in sorted(linhas)]


# ---------------------------------------------------------------------------------------------
# Modelo (TMDL)


def etiqueta(*partes: str) -> str:
    return str(uuid.uuid5(ESPACO, "/".join(partes)))


def nome_tmdl(nome: str) -> str:
    return nome if NOME_SIMPLES.fullmatch(nome) else "'" + nome.replace("'", "''") + "'"


def descricao_tmdl(texto: str, recuo: int) -> list[str]:
    return ["\t" * recuo + "/// " + linha if linha else "\t" * recuo + "///" for linha in texto.splitlines()]


def expressao_tmdl(cabecalho: str, expressao: str, recuo: int) -> list[str]:
    """Uma expressão de uma linha fica na mesma linha; a de várias, dois níveis abaixo."""
    if "\n" not in expressao:
        return [f"{cabecalho} = {expressao}"]
    corpo = ["\t" * recuo + linha if linha.strip() else "" for linha in expressao.splitlines()]
    return [f"{cabecalho} =", *corpo]


def tipo_do_resultado(consulta: dict) -> str:
    if "IsParameterQuery = true" in consulta["m"]:
        return "Text"
    if consulta["nome"].startswith("fn_"):
        return "Function"
    return "Table"


def formato_da_medida(nome: str) -> str | None:
    if nome in SEM_FORMATO:
        return None
    if nome in FORMATO_PERCENTUAL:
        return "0.0%"
    if nome in FORMATO_DATA:
        return "dd/MM/yyyy"
    return "0"


def tabela_tmdl(consulta: dict, medidas: list[dict]) -> str:
    nome = consulta["nome"]
    linhas = [*descricao_tmdl(consulta["descricao"], 0), f"table {nome_tmdl(nome)}"]
    if TABELA_DE_DATAS[0] == nome:
        linhas.append("\tdataCategory: Time")
    linhas += [f"\tlineageTag: {etiqueta('tabela', nome)}", ""]

    for medida in medidas if nome == "Medidas" else []:
        linhas += descricao_tmdl(medida["descricao"], 1)
        linhas += expressao_tmdl(f"\tmeasure {nome_tmdl(medida['nome'])}", medida["expressao"], 3)
        formato = formato_da_medida(medida["nome"])
        if formato:
            linhas.append(f"\t\tformatString: {formato}")
        linhas += [f"\t\tlineageTag: {etiqueta('medida', medida['nome'])}", ""]

    for coluna, tipo in COLUNAS[nome]:
        linhas += [f"\tcolumn {nome_tmdl(coluna)}", f"\t\tdataType: {tipo}"]
        if (nome, coluna) in ESCONDIDAS:
            linhas.append("\t\tisHidden")
        if (nome, coluna) == TABELA_DE_DATAS:
            linhas.append("\t\tisKey")
        if tipo == DATA:
            linhas.append("\t\tformatString: dd/MM/yyyy")
        elif tipo == INTEIRO:
            linhas.append("\t\tformatString: 0")
        linhas += [
            f"\t\tlineageTag: {etiqueta('coluna', nome, coluna)}",
            "\t\tsummarizeBy: none",
            f"\t\tsourceColumn: {coluna}",
        ]
        if (nome, coluna) in CLASSIFICAR_POR:
            linhas.append(f"\t\tsortByColumn: {CLASSIFICAR_POR[(nome, coluna)]}")
        linhas.append("")
        if tipo == DATA:
            linhas += ["\t\tannotation UnderlyingDateTimeDataType = Date", ""]
        linhas += ["\t\tannotation SummarizationSetBy = User", ""]

    linhas += [f"\tpartition {nome_tmdl(nome)} = m", "\t\tmode: import"]
    linhas += expressao_tmdl("\t\tsource", consulta["m"], 4)
    linhas += ["", "\tannotation PBI_ResultType = Table", ""]
    return "\n".join(linhas)


def expressoes_tmdl(consultas: list[dict], pasta_entrada: str) -> str:
    linhas = []
    for consulta in consultas:
        if consulta["carrega"]:
            continue
        m = consulta["m"]
        if consulta["nome"] == "PastaEntrada":
            m, trocas = re.subn(r'^"[^"]*"', lambda _: '"' + pasta_entrada.replace('"', '""') + '"', m, count=1)
            if trocas != 1:
                sys.exit("PastaEntrada.m precisa começar pelo caminho entre aspas")
        linhas += descricao_tmdl(consulta["descricao"], 0)
        linhas += expressao_tmdl(f"expression {nome_tmdl(consulta['nome'])}", m, 2)
        linhas += [
            f"\tlineageTag: {etiqueta('expressao', consulta['nome'])}",
            "",
            f"\tannotation PBI_ResultType = {tipo_do_resultado(consulta)}",
            "",
        ]
    return "\n".join(linhas)


def modelo_tmdl(consultas: list[dict]) -> str:
    ordem = json.dumps([consulta["nome"] for consulta in consultas], ensure_ascii=False)
    linhas = [
        "model Model",
        "\tculture: pt-BR",
        "\tdefaultPowerBIDataSourceVersion: powerBI_V3",
        "\tsourceQueryCulture: pt-BR",
        "\tdataAccessOptions",
        "\t\tlegacyRedirects",
        "\t\treturnErrorValuesAsNull",
        "",
        f"annotation PBI_QueryOrder = {ordem}",
        "",
        # Passo 2 de MONTAGEM.md: sem a tabela de datas automática para cada coluna de data.
        "annotation __PBI_TimeIntelligenceEnabled = 0",
        "",
        'annotation PBI_ProTooling = ["DevMode"]',
        "",
    ]
    linhas += [f"ref table {nome_tmdl(c['nome'])}" for c in consultas if c["carrega"]]
    return "\n".join(linhas) + "\n"


def relacoes_tmdl(relacoes) -> str:
    linhas = []
    for muitos, coluna_muitos, um, coluna_um in relacoes:
        linhas.append(f"relationship {etiqueta('relacao', muitos, coluna_muitos, um, coluna_um)}")
        if (um, coluna_um) == TABELA_DE_DATAS:
            linhas.append("\tjoinOnDateBehavior: datePartOnly")
        linhas += [f"\tfromColumn: {muitos}.{coluna_muitos}", f"\ttoColumn: {um}.{coluna_um}", ""]
    return "\n".join(linhas)


def escrever_modelo(pasta: Path, pasta_entrada: str) -> None:
    consultas = ler_consultas()
    medidas = ler_medidas()
    carregadas = [c["nome"] for c in consultas if c["carrega"]]
    if sorted(carregadas) != sorted(COLUNAS):
        sys.exit(f"as consultas carregadas {sorted(carregadas)} não são as tabelas de COLUNAS")
    escrever_json(pasta / "definition.pbism", {
        "$schema": ESQUEMAS + "item/semanticModel/definitionProperties/1.0.0/schema.json",
        "version": "4.2",
        "settings": {},
    })
    definicao = pasta / "definition"
    escrever(definicao / "database.tmdl", "database\n\tcompatibilityLevel: 1600\n")
    escrever(definicao / "model.tmdl", modelo_tmdl(consultas))
    escrever(definicao / "expressions.tmdl", expressoes_tmdl(consultas, pasta_entrada))
    escrever(definicao / "relationships.tmdl", relacoes_tmdl(ler_relacoes()))
    for consulta in consultas:
        if consulta["carrega"]:
            escrever(definicao / "tables" / f"{consulta['nome']}.tmdl", tabela_tmdl(consulta, medidas))


# ---------------------------------------------------------------------------------------------
# Relatório (PBIR)


def coluna(tabela: str, nome: str) -> dict:
    return {"Column": {"Expression": {"SourceRef": {"Entity": tabela}}, "Property": nome}}


def medida(nome: str) -> dict:
    return {"Measure": {"Expression": {"SourceRef": {"Entity": "Medidas"}}, "Property": nome}}


def referencia(campo: dict) -> str:
    dados = next(iter(campo.values()))
    return f"{dados['Expression']['SourceRef']['Entity']}.{dados['Property']}"


def projecao(campo: dict, rotulo: str | None = None) -> dict:
    resultado = {"field": campo, "queryRef": referencia(campo), "nativeQueryRef": next(iter(campo.values()))["Property"]}
    if rotulo:
        resultado["displayName"] = rotulo
    return resultado


def literal(valor: str) -> dict:
    return {"expr": {"Literal": {"Value": valor}}}


def texto_literal(texto: str) -> dict:
    return literal("'" + texto.replace("'", "''") + "'")


def titulo(texto: str) -> dict:
    return {"title": [{"properties": {"show": literal("true"), "text": texto_literal(texto)}}]}


def cor_por_campo(valor: str) -> list[dict]:
    """Formatação condicional: o fundo da célula vem do texto da medida Cor Farol."""
    return [{
        "properties": {"backColor": {"solid": {"color": {"expr": medida("Cor Farol")}}}},
        "selector": {"data": [{"dataViewWildcard": {"matchingOption": 1}}], "metadata": valor},
    }]


def fonte_do_filtro(campo: dict, apelido: str) -> tuple[list[dict], dict]:
    tipo, dados = next(iter(campo.items()))
    origem = [{"Name": apelido, "Entity": dados["Expression"]["SourceRef"]["Entity"], "Type": 0}]
    local = {tipo: {"Expression": {"SourceRef": {"Source": apelido}}, "Property": dados["Property"]}}
    return origem, local


def filtro_igual(nome: str, campo: dict, valor: str, tipo: str) -> dict:
    origem, local = fonte_do_filtro(campo, "f")
    if tipo == "Categorical":
        condicao = {"In": {"Expressions": [local], "Values": [[{"Literal": {"Value": valor}}]]}}
    else:
        condicao = {"Comparison": {"ComparisonKind": 0, "Left": local, "Right": {"Literal": {"Value": valor}}}}
    return {
        "name": nome,
        "field": campo,
        "type": tipo,
        "filter": {"Version": 2, "From": origem, "Where": [{"Condition": condicao}]},
        "howCreated": "User",
    }


def filtro_entre(nome: str, campo: dict, minimo: str, maximo: str) -> dict:
    origem, local = fonte_do_filtro(campo, "f")
    condicao = {"And": {
        "Left": {"Comparison": {"ComparisonKind": 2, "Left": local, "Right": {"Literal": {"Value": minimo}}}},
        "Right": {"Comparison": {"ComparisonKind": 4, "Left": local, "Right": {"Literal": {"Value": maximo}}}},
    }}
    return {
        "name": nome,
        "field": campo,
        "type": "Advanced",
        "filter": {"Version": 2, "From": origem, "Where": [{"Condition": condicao}]},
        "howCreated": "User",
    }


class Pagina:
    def __init__(self, nome: str, titulo_da_pagina: str):
        self.nome = nome
        self.titulo = titulo_da_pagina
        self.visuais: list[dict] = []

    def adicionar(self, nome, x, y, largura, altura, tipo, *, papeis=None, ordem=None, objetos=None,
                  container=None, filtros=None, sincronia=None) -> None:
        visual = {"visualType": tipo}
        if papeis:
            visual["query"] = {"queryState": {papel: {"projections": lista} for papel, lista in papeis.items()}}
            if ordem:
                visual["query"]["sortDefinition"] = {
                    "sort": [{"field": campo, "direction": direcao} for campo, direcao in ordem],
                    "isDefaultSort": False,
                }
        if objetos:
            visual["objects"] = objetos
        if container:
            visual["visualContainerObjects"] = container
        if sincronia:
            visual["syncGroup"] = {"groupName": sincronia, "fieldChanges": True, "filterChanges": True}
        visual["drillFilterOtherVisuals"] = True
        posicao = len(self.visuais)
        conteudo = {
            "$schema": f"{ESQUEMAS}item/report/definition/visualContainer/{VERSOES['visual']}/schema.json",
            "name": nome,
            "position": {"x": x, "y": y, "z": posicao, "height": altura, "width": largura, "tabOrder": posicao},
            "visual": visual,
        }
        if filtros:
            conteudo["filterConfig"] = {"filters": filtros}
        self.visuais.append(conteudo)

    def texto(self, nome, x, y, largura, altura, paragrafos) -> None:
        self.adicionar(nome, x, y, largura, altura, "textbox", objetos={"general": [{"properties": {"paragraphs": paragrafos}}]})

    def cabecalho(self) -> None:
        self.texto("titulo", 20, 8, 820, 60, [
            {"textRuns": [{"value": self.titulo, "textStyle": {"fontWeight": "bold", "fontSize": "18pt"}}]},
            {"textRuns": [{
                "value": "Dados sintéticos. As regras de obrigatoriedade são parâmetros do modelo, "
                         "não interpretação jurídica das NRs.",
                "textStyle": {"fontSize": "9pt", "color": "#5D6D7E"},
            }]},
        ])

    def filtros_de_equipe_e_funcao(self) -> None:
        for nome, x, campo, rotulo in (
            ("filtro_equipe", 860, coluna("dim_equipe", "equipe"), "Equipe"),
            ("filtro_funcao", 1070, coluna("dim_funcao", "funcao"), "Função"),
        ):
            self.adicionar(
                nome, x, 10, 190, 56, "slicer",
                papeis={"Values": [projecao(campo, rotulo)]},
                objetos={"data": [{"properties": {"mode": texto_literal("Dropdown")}}]},
                sincronia=nome,
            )


def cartao(pagina: Pagina, nome: str, x, y, largura, altura, nome_da_medida: str) -> None:
    pagina.adicionar(nome, x, y, largura, altura, "card", papeis={"Values": [projecao(medida(nome_da_medida))]})


def pagina_visao_geral() -> Pagina:
    pagina = Pagina("visao_geral", "Visão geral")
    pagina.cabecalho()
    pagina.filtros_de_equipe_e_funcao()
    cartoes = [
        "Data de Referência", "Funcionários Ativos", "Funcionários Irregulares", "% Conformidade",
        "Pendentes Obrigatórios", "Vencidos", "Vencem em 30 dias", "Vencem em 60 dias", "Vencem em 90 dias",
    ]
    for posicao, nome in enumerate(cartoes):
        cartao(pagina, f"cartao_{posicao + 1}", 20 + posicao * 138, 80, 130, 100, nome)
    pagina.adicionar(
        "conformidade_por_funcao", 20, 195, 610, 505, "clusteredBarChart",
        papeis={
            "Category": [projecao(coluna("dim_funcao", "funcao"), "Função")],
            "Y": [projecao(medida("% Conformidade"))],
        },
        ordem=[(medida("% Conformidade"), "Ascending")],
        objetos={"labels": [{"properties": {"show": literal("true")}}]},
        container=titulo("Conformidade por função (itens obrigatórios em dia)"),
    )
    pagina.adicionar(
        "vencimentos_por_mes", 650, 195, 610, 505, "clusteredColumnChart",
        papeis={
            "Category": [projecao(coluna("dim_calendario", "mes_ano"), "Mês")],
            "Y": [projecao(medida("Itens com Vencimento"))],
        },
        ordem=[(coluna("dim_calendario", "mes_ano"), "Ascending")],
        objetos={"labels": [{"properties": {"show": literal("true")}}]},
        container=titulo("Itens que vencem por mês, nos 12 meses a partir da data de referência"),
        filtros=[filtro_entre("doze_meses", coluna("dim_calendario", "meses_da_referencia"), "0L", "11L")],
    )
    return pagina


def pagina_matriz_farol() -> Pagina:
    pagina = Pagina("matriz_farol", "Matriz farol")
    pagina.cabecalho()
    pagina.filtros_de_equipe_e_funcao()
    legenda = []
    for situacao, cor in ler_farol():
        legenda += [
            {"value": "■ ", "textStyle": {"color": cor, "fontSize": "12pt"}},
            {"value": f"{situacao}    ", "textStyle": {"fontSize": "9pt"}},
        ]
    pagina.texto("legenda", 20, 72, 1240, 36, [{"textRuns": legenda}])
    pagina.adicionar(
        "matriz", 20, 112, 1240, 596, "pivotTable",
        papeis={
            "Rows": [projecao(coluna("dim_funcionario", "funcionario"), "Funcionário")],
            "Columns": [projecao(coluna("dim_treinamento", "codigo"), "Treinamento")],
            "Values": [projecao(medida("Rótulo Farol"), "Situação")],
        },
        objetos={
            "subTotals": [{"properties": {"rowSubtotals": literal("false"), "columnSubtotals": literal("false")}}],
            "values": cor_por_campo("Medidas.Rótulo Farol"),
        },
        filtros=[filtro_igual("so_ativos", coluna("dim_funcionario", "situacao"), "'Ativo'", "Categorical")],
    )
    return pagina


def pagina_agenda() -> Pagina:
    pagina = Pagina("agenda", "Agenda de reciclagem")
    pagina.cabecalho()
    pagina.filtros_de_equipe_e_funcao()
    colunas = [
        (medida("Vencimento do Item"), "Vencimento"),
        (medida("Dias para Vencer"), "Dias"),
        (coluna("dim_funcionario", "matricula"), "Matrícula"),
        (coluna("dim_funcionario", "nome"), "Nome"),
        (coluna("dim_funcionario", "funcao"), "Função"),
        (coluna("dim_funcionario", "equipe"), "Equipe"),
        (coluna("dim_treinamento", "codigo"), "Treinamento"),
        (coluna("dim_treinamento", "nome"), "Descrição"),
        (medida("Emissão do Item"), "Emissão"),
        (medida("Status Farol"), "Situação"),
    ]
    pagina.adicionar(
        "agenda", 20, 80, 1240, 628, "tableEx",
        papeis={"Values": [projecao(campo, rotulo) for campo, rotulo in colunas]},
        ordem=[(medida("Vencimento do Item"), "Ascending")],
        objetos={
            "total": [{"properties": {"totals": literal("false")}}],
            "values": cor_por_campo("Medidas.Status Farol"),
        },
        container=titulo("O que vence entre a data de referência e o fim da maior janela"),
        filtros=[filtro_igual("na_agenda", medida("Na Agenda"), "1L", "Advanced")],
    )
    return pagina


def pagina_qualidade() -> Pagina:
    pagina = Pagina("qualidade", "Qualidade dos dados")
    pagina.cabecalho()
    cartao(pagina, "cartao_rejeitadas", 20, 80, 200, 100, "Linhas Rejeitadas")
    pagina.texto("explicacao", 240, 80, 1020, 100, [{"textRuns": [{
        "value": "Cada linha é algo que a limpeza deixou de fora. Corrija na planilha de origem e clique em Atualizar.",
        "textStyle": {"fontSize": "12pt"},
    }]}])
    colunas = [
        ("aba", "Aba"), ("linha", "Linha"), ("matricula", "Matrícula"), ("coluna", "Coluna"),
        ("valor_original", "Valor original"), ("motivo", "Motivo"), ("acao", "Ação"),
    ]
    pagina.adicionar(
        "rejeicoes", 20, 195, 1240, 250, "tableEx",
        papeis={"Values": [projecao(coluna("qualidade_rejeicoes", nome), rotulo) for nome, rotulo in colunas]},
        objetos={"total": [{"properties": {"totals": literal("false")}}]},
        container=titulo("Linhas rejeitadas na limpeza"),
    )
    pagina.adicionar(
        "rejeicoes_por_motivo", 20, 460, 1240, 248, "clusteredBarChart",
        papeis={
            "Category": [projecao(coluna("qualidade_rejeicoes", "motivo"), "Motivo")],
            "Y": [projecao(medida("Linhas Rejeitadas"))],
        },
        objetos={"labels": [{"properties": {"show": literal("true")}}]},
        container=titulo("Rejeições por motivo"),
    )
    return pagina


def escrever_relatorio(pasta: Path) -> None:
    escrever_json(pasta / "definition.pbir", {
        "$schema": ESQUEMAS + "item/report/definitionProperties/2.0.0/schema.json",
        "version": "4.0",
        "datasetReference": {"byPath": {"path": f"../{NOME}.SemanticModel"}},
    })
    definicao = pasta / "definition"
    escrever_json(definicao / "version.json", {
        "$schema": ESQUEMAS + "item/report/definition/versionMetadata/1.0.0/schema.json",
        "version": "2.0.0",
    })
    escrever_json(definicao / "report.json", {
        "$schema": f"{ESQUEMAS}item/report/definition/report/{VERSOES['report']}/schema.json",
        "themeCollection": {"customTheme": {"name": "tema.json", "reportVersionAtImport": VERSOES, "type": "RegisteredResources"}},
        "resourcePackages": [{
            "name": "RegisteredResources",
            "type": "RegisteredResources",
            "items": [{"name": "tema.json", "path": "tema.json", "type": "CustomTheme"}],
        }],
        "settings": {
            "useStylableVisualContainerHeader": True,
            "defaultDrillFilterOtherVisuals": True,
            "useEnhancedTooltips": True,
        },
    })
    tema = pasta / "StaticResources" / "RegisteredResources" / "tema.json"
    tema.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(TEMA, tema)

    paginas = [pagina_visao_geral(), pagina_matriz_farol(), pagina_agenda(), pagina_qualidade()]
    escrever_json(definicao / "pages" / "pages.json", {
        "$schema": ESQUEMAS + "item/report/definition/pagesMetadata/1.0.0/schema.json",
        "pageOrder": [pagina.nome for pagina in paginas],
        "activePageName": paginas[0].nome,
    })
    for pagina in paginas:
        pasta_da_pagina = definicao / "pages" / pagina.nome
        escrever_json(pasta_da_pagina / "page.json", {
            "$schema": f"{ESQUEMAS}item/report/definition/page/{VERSOES['page']}/schema.json",
            "name": pagina.nome,
            "displayName": pagina.titulo,
            "displayOption": "FitToPage",
            "height": 720,
            "width": 1280,
        })
        for visual in pagina.visuais:
            escrever_json(pasta_da_pagina / "visuals" / visual["name"] / "visual.json", visual)


# ---------------------------------------------------------------------------------------------
# Arquivos


def escrever(caminho: Path, texto: str) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(texto, encoding="utf-8", newline="\n")


def escrever_json(caminho: Path, dados) -> None:
    escrever(caminho, json.dumps(dados, ensure_ascii=False, indent=2) + "\n")


def montar(saida: Path, pasta_entrada: str) -> None:
    # Só apaga o que este script cria; o que o Power BI Desktop guarda em .pbi/ fica.
    for parte in (f"{NOME}.SemanticModel/definition", f"{NOME}.Report/definition", f"{NOME}.Report/StaticResources"):
        if (saida / parte).exists():
            shutil.rmtree(saida / parte)
    escrever_json(saida / f"{NOME}.pbip", {
        "$schema": ESQUEMAS + "pbip/pbipProperties/1.0.0/schema.json",
        "version": "1.0",
        "artifacts": [{"report": {"path": f"{NOME}.Report"}}],
        "settings": {"enableAutoRecovery": True},
    })
    escrever(saida / ".gitignore", "# O Power BI Desktop guarda aqui o cache dos dados e as preferências locais.\n**/.pbi/\n")
    escrever_modelo(saida / f"{NOME}.SemanticModel", pasta_entrada)
    escrever_relatorio(saida / f"{NOME}.Report")


def main() -> None:
    argumentos = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    argumentos.add_argument("--saida", type=Path, default=SAIDA_PADRAO, help="pasta do projeto (padrão: powerbi/)")
    argumentos.add_argument(
        "--pasta-entrada", default=CAMINHO_DE_EXEMPLO,
        help="caminho completo da pasta data/entrada, gravado no parâmetro PastaEntrada",
    )
    opcoes = argumentos.parse_args()
    montar(opcoes.saida.resolve(), opcoes.pasta_entrada)
    print(f"Projeto gravado em {opcoes.saida}. Abra {NOME}.pbip no Power BI Desktop.")


if __name__ == "__main__":
    main()
