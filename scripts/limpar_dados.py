"""Limpa as planilhas de entrada e grava a versão limpa em CSV.

É a limpeza que o Power Query vai repetir no painel: tira espaços sobrando,
converte datas escritas como texto, descarta a segunda linha de uma matrícula
repetida e a célula com data impossível, e passa a planilha larga (uma coluna
por treinamento) para o formato longo (uma linha por emissão). Tudo o que for
descartado fica registrado em qualidade_rejeicoes.csv, com o motivo.

Saída, na pasta indicada em --saida:
  dim_funcionario.csv           uma linha por matrícula
  dim_funcao.csv                as funções que têm regra
  dim_treinamento.csv           código, nome e validade em meses
  regra_funcao_treinamento.csv  SIM, NÃO ou CONDICIONAL, uma linha por par
  fato_certificacao.csv         uma linha por emissão, da aba Controle e da Historico
  parametro.csv                 data de referência e janelas de alerta
  qualidade_rejeicoes.csv       o que foi descartado e por quê

Uso:
  python scripts/limpar_dados.py
  python scripts/limpar_dados.py --entrada outra/entrada --saida outra/limpa
"""
from __future__ import annotations

import argparse
import csv
import re
import sys
from datetime import date, datetime
from pathlib import Path

from openpyxl import load_workbook

RAIZ = Path(__file__).resolve().parents[1]
ENTRADA_PADRAO = RAIZ / "data" / "entrada"
SAIDA_PADRAO = RAIZ / "data" / "limpa"

CONTROLE = "controle_largo.xlsx"
PARAMETROS = "parametros.xlsx"

# Cabeçalho da planilha -> coluna do CSV.
CADASTRO = {
    "Matrícula": "matricula",
    "Nome": "nome",
    "Função": "funcao",
    "Equipe": "equipe",
    "Admissão": "admissao",
    "Situação": "situacao",
    "Desligamento": "desligamento",
}
DATAS_DO_CADASTRO = ("Admissão", "Desligamento")
ALERTAS = {
    "Data de referência": "data_referencia",
    "Janela de alerta 1 (dias)": "janela_1",
    "Janela de alerta 2 (dias)": "janela_2",
    "Janela de alerta 3 (dias)": "janela_3",
}
REGRAS_VALIDAS = {"SIM", "NÃO", "CONDICIONAL"}

DATA_EM_TEXTO = re.compile(r"(\d{2})/(\d{2})/(\d{4})")

COLUNAS_REJEICAO = ["aba", "linha", "matricula", "coluna", "valor_original", "motivo", "acao"]


class ErroDeEntrada(Exception):
    """A planilha não tem o formato esperado; a limpeza para e explica."""


class DataInvalida(ValueError):
    pass


def limpar_texto(valor) -> str:
    """Tira espaços nas pontas e espaços repetidos no meio."""
    return "" if valor is None else " ".join(str(valor).split())


def ler_data(valor) -> date | None:
    """Aceita data do Excel ou texto dd/mm/aaaa; vazio vira None."""
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    texto = limpar_texto(valor)
    if not texto:
        return None
    casamento = DATA_EM_TEXTO.fullmatch(texto)
    if not casamento:
        raise DataInvalida(valor)
    dia, mes, ano = (int(parte) for parte in casamento.groups())
    try:
        return date(ano, mes, dia)
    except ValueError:
        raise DataInvalida(valor) from None


def iso(data: date | None) -> str:
    return "" if data is None else data.isoformat()


def ler_aba(caminho: Path, aba: str) -> tuple[list[str], list[tuple[int, dict]]]:
    """Devolve o cabeçalho limpo e as linhas como (número no Excel, {coluna: valor})."""
    planilha = load_workbook(caminho, read_only=True, data_only=True)
    try:
        if aba not in planilha.sheetnames:
            raise ErroDeEntrada(f"{caminho.name} não tem a aba {aba!r}")
        linhas = list(planilha[aba].iter_rows(values_only=True))
    finally:
        planilha.close()
    if not linhas:
        raise ErroDeEntrada(f"a aba {aba!r} de {caminho.name} está vazia")
    cabecalho = [limpar_texto(celula) for celula in linhas[0]]
    corpo = [
        (numero, dict(zip(cabecalho, linha)))
        for numero, linha in enumerate(linhas[1:], start=2)
        if any(celula is not None for celula in linha)
    ]
    return cabecalho, corpo


def exigir_colunas(cabecalho: list[str], colunas, onde: str) -> None:
    faltando = [coluna for coluna in colunas if coluna not in cabecalho]
    if faltando:
        raise ErroDeEntrada(f"{onde} não tem {', '.join(faltando)}")


def ler_matricula(valor, onde: str) -> int:
    texto = limpar_texto(valor)
    if not texto.isdigit():
        raise ErroDeEntrada(f"{onde}: matrícula {valor!r} não é um número")
    return int(texto)


def limpar_parametros(caminho: Path) -> dict[str, list[dict]]:
    cabecalho, linhas = ler_aba(caminho, "Treinamentos")
    exigir_colunas(cabecalho, ["Código", "Treinamento", "Validade (meses)"], "a aba Treinamentos")
    treinamentos = [
        {
            "codigo": limpar_texto(linha["Código"]),
            "nome": limpar_texto(linha["Treinamento"]),
            "validade_meses": int(linha["Validade (meses)"]),
        }
        for _, linha in linhas
    ]
    codigos = [treinamento["codigo"] for treinamento in treinamentos]

    cabecalho, linhas = ler_aba(caminho, "Regra_Funcao_Treinamento")
    exigir_colunas(cabecalho, ["Função", *codigos], "a aba Regra_Funcao_Treinamento")
    funcoes, regras = [], []
    for numero, linha in linhas:
        funcao = limpar_texto(linha["Função"])
        funcoes.append({"funcao": funcao})
        for codigo in codigos:
            regra = limpar_texto(linha[codigo]).upper()
            if regra not in REGRAS_VALIDAS:
                raise ErroDeEntrada(
                    f"Regra_Funcao_Treinamento, linha {numero}, {codigo}: "
                    f"{linha[codigo]!r} não é SIM, NÃO nem CONDICIONAL"
                )
            regras.append({"funcao": funcao, "treinamento": codigo, "regra": regra})

    _, linhas = ler_aba(caminho, "Alertas")
    valores = {limpar_texto(linha["Parâmetro"]): linha["Valor"] for _, linha in linhas}
    exigir_colunas(list(valores), ALERTAS, "a aba Alertas")
    parametro = {
        "data_referencia": iso(ler_data(valores["Data de referência"])),
        **{
            coluna: int(valores[rotulo])
            for rotulo, coluna in ALERTAS.items()
            if coluna != "data_referencia"
        },
    }
    return {
        "dim_treinamento": treinamentos,
        "dim_funcao": funcoes,
        "regra_funcao_treinamento": regras,
        "parametro": [parametro],
    }


def limpar_controle(caminho: Path, codigos: list[str]) -> dict[str, list[dict]]:
    rejeicoes: list[dict] = []

    def rejeitar(aba, numero, matricula, coluna, valor, motivo, acao):
        rejeicoes.append(dict(zip(COLUNAS_REJEICAO, (
            aba, numero, matricula, coluna, "" if valor is None else str(valor), motivo, acao,
        ))))

    cabecalho, linhas = ler_aba(caminho, "Controle")
    exigir_colunas(cabecalho, [*CADASTRO, *codigos], "a aba Controle")
    funcionarios: dict[int, dict] = {}
    emissoes: list[dict] = []
    for numero, linha in linhas:
        matricula = ler_matricula(linha["Matrícula"], f"Controle, linha {numero}")
        if matricula in funcionarios:
            # Fica a primeira ocorrência; a repetida sai inteira, inclusive as datas.
            rejeitar("Controle", numero, matricula, "Matrícula", matricula,
                     "Matrícula duplicada", "Linha descartada")
            continue

        datas = {}
        for coluna in [*DATAS_DO_CADASTRO, *codigos]:
            try:
                datas[coluna] = ler_data(linha[coluna])
            except DataInvalida:
                datas[coluna] = None
                rejeitar("Controle", numero, matricula, coluna, linha[coluna],
                         "Data inválida", "Célula descartada")

        funcionarios[matricula] = {
            CADASTRO[coluna]: iso(datas[coluna]) if coluna in DATAS_DO_CADASTRO
            else limpar_texto(linha[coluna])
            for coluna in CADASTRO
        }
        funcionarios[matricula]["matricula"] = matricula
        emissoes += [
            {"matricula": matricula, "treinamento": codigo,
             "data_emissao": iso(datas[codigo]), "origem": "Controle"}
            for codigo in codigos
            if datas[codigo] is not None
        ]

    cabecalho, linhas = ler_aba(caminho, "Historico")
    exigir_colunas(cabecalho, ["Matrícula", "Treinamento", "Data de emissão"], "a aba Historico")
    for numero, linha in linhas:
        matricula = ler_matricula(linha["Matrícula"], f"Historico, linha {numero}")
        try:
            data = ler_data(linha["Data de emissão"])
        except DataInvalida:
            rejeitar("Historico", numero, matricula, "Data de emissão", linha["Data de emissão"],
                     "Data inválida", "Linha descartada")
            continue
        if data is None:
            rejeitar("Historico", numero, matricula, "Data de emissão", None,
                     "Data vazia", "Linha descartada")
            continue
        emissoes.append({"matricula": matricula, "treinamento": limpar_texto(linha["Treinamento"]),
                         "data_emissao": iso(data), "origem": "Historico"})

    emissoes.sort(key=lambda e: (e["matricula"], e["treinamento"], e["data_emissao"]))
    return {
        "dim_funcionario": [funcionarios[matricula] for matricula in sorted(funcionarios)],
        "fato_certificacao": emissoes,
        "qualidade_rejeicoes": rejeicoes,
    }


COLUNAS = {
    "dim_funcionario": list(CADASTRO.values()),
    "dim_funcao": ["funcao"],
    "dim_treinamento": ["codigo", "nome", "validade_meses"],
    "regra_funcao_treinamento": ["funcao", "treinamento", "regra"],
    "fato_certificacao": ["matricula", "treinamento", "data_emissao", "origem"],
    "parametro": ["data_referencia", "janela_1", "janela_2", "janela_3"],
    "qualidade_rejeicoes": COLUNAS_REJEICAO,
}


def gravar_csv(caminho: Path, colunas: list[str], linhas: list[dict]) -> None:
    # UTF-8 e \n fixos: a mesma entrada dá os mesmos bytes em qualquer sistema.
    with open(caminho, "w", encoding="utf-8", newline="") as arquivo:
        escritor = csv.writer(arquivo, lineterminator="\n")
        escritor.writerow(colunas)
        escritor.writerows([linha[coluna] for coluna in colunas] for linha in linhas)


def limpar(entrada: Path) -> dict[str, list[dict]]:
    for nome in (CONTROLE, PARAMETROS):
        if not (entrada / nome).is_file():
            raise ErroDeEntrada(f"não achei {entrada / nome}")
    tabelas = limpar_parametros(entrada / PARAMETROS)
    codigos = [treinamento["codigo"] for treinamento in tabelas["dim_treinamento"]]
    tabelas.update(limpar_controle(entrada / CONTROLE, codigos))
    return tabelas


def resumir(tabelas: dict[str, list[dict]], saida: Path) -> list[str]:
    linhas = [f"Versão limpa gravada em {saida}:"]
    linhas += [f"  {nome}.csv: {len(tabelas[nome])} linhas" for nome in COLUNAS]
    linhas.append(f"Rejeições ({len(tabelas['qualidade_rejeicoes'])}):")
    for r in tabelas["qualidade_rejeicoes"]:
        celula = f", {r['coluna']} = {r['valor_original']!r}" if r["motivo"] != "Matrícula duplicada" else ""
        linhas.append(
            f"  {r['aba']}, linha {r['linha']}, matrícula {r['matricula']}{celula}: "
            f"{r['motivo']} ({r['acao']})"
        )
    return linhas


def main() -> None:
    # Sem isso, o Windows escreve os acentos das mensagens em cp1252.
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Limpa as planilhas de entrada do painel.")
    parser.add_argument("--entrada", type=Path, default=ENTRADA_PADRAO)
    parser.add_argument("--saida", type=Path, default=SAIDA_PADRAO)
    args = parser.parse_args()

    try:
        tabelas = limpar(args.entrada)
    except ErroDeEntrada as erro:
        sys.exit(f"erro: {erro}")

    args.saida.mkdir(parents=True, exist_ok=True)
    for nome, colunas in COLUNAS.items():
        gravar_csv(args.saida / f"{nome}.csv", colunas, tabelas[nome])
    print("\n".join(resumir(tabelas, args.saida)))


if __name__ == "__main__":
    main()
