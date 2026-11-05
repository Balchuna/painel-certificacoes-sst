"""Leitura independente das planilhas, usada só pelos testes.

Nada aqui importa o gerador. Os testes abrem a planilha como um terceiro
abriria e tiram as próprias conclusões, assim um erro do gerador não se
esconde atrás do próprio gerador.
"""
from __future__ import annotations

import calendar
import os
import re
import subprocess
import sys
from datetime import date, datetime
from pathlib import Path

import openpyxl

RAIZ = Path(__file__).resolve().parents[1]
SCRIPT = RAIZ / "scripts" / "gerar_dados.py"
ENTRADA_VERSIONADA = RAIZ / "data" / "entrada"

CONTROLE = "controle_largo.xlsx"
PARAMETROS = "parametros.xlsx"

DATA_REF = date(2026, 11, 1)

# Os 12 códigos e as 5 funções da aba Config_SST da referência.
TREINAMENTOS = [
    "ASO", "NR01", "NR05", "NR06", "NR12", "NR18",
    "NR34", "NR35", "PEMT1", "PEMT2", "ANDAIME", "CARTEIRA",
]
FUNCOES = {
    "MONTADOR DE STEEL FRAME",
    "AJ. DE MONTADOR DE STEEL FRAME",
    "ENCARREGADO DE OBRAS",
    "MONTADOR DE GESSO",
    "TEC. DE SEGURANÇA DO TRABALHO",
}
COLUNAS_CADASTRO = [
    "Matrícula", "Nome", "Função", "Equipe", "Admissão", "Situação", "Desligamento",
]
COLUNAS_DATA = ["Admissão", "Desligamento", *TREINAMENTOS]

INVALIDA = "DATA INVÁLIDA"


def rodar_gerador(saida, *args, hash_seed="0"):
    """Roda o gerador como um usuário rodaria: pela linha de comando."""
    ambiente = {**os.environ, "PYTHONHASHSEED": hash_seed}
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--saida", str(saida), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=ambiente,
    )


def gerar_ok(saida, *args, hash_seed="0"):
    resultado = rodar_gerador(saida, *args, hash_seed=hash_seed)
    assert resultado.returncode == 0, resultado.stderr
    return resultado


def ler_aba(caminho, aba):
    """Devolve a aba como lista de dicionários {cabeçalho: valor da célula}."""
    planilha = openpyxl.load_workbook(caminho, data_only=True)
    try:
        linhas = list(planilha[aba].iter_rows(values_only=True))
    finally:
        planilha.close()
    cabecalho = linhas[0]
    return [dict(zip(cabecalho, linha)) for linha in linhas[1:]]


def ler_validades(pasta):
    """{código do treinamento: validade em meses}."""
    linhas = ler_aba(pasta / PARAMETROS, "Treinamentos")
    return {linha["Código"]: linha["Validade (meses)"] for linha in linhas}


def ler_regras(pasta):
    """{função: {código do treinamento: SIM, NÃO ou CONDICIONAL}}."""
    linhas = ler_aba(pasta / PARAMETROS, "Regra_Funcao_Treinamento")
    return {
        linha["Função"]: {k: v for k, v in linha.items() if k != "Função"}
        for linha in linhas
    }


def ler_todas_as_celulas(caminho):
    """Devolve {aba: [linhas]} para comparar duas planilhas célula a célula."""
    planilha = openpyxl.load_workbook(caminho, data_only=True)
    try:
        return {
            aba: [list(linha) for linha in planilha[aba].iter_rows(values_only=True)]
            for aba in planilha.sheetnames
        }
    finally:
        planilha.close()


def limpar_texto(valor):
    """Tira espaços nas pontas e espaços repetidos no meio."""
    return " ".join(str(valor).split())


def interpretar_data(valor):
    """Devolve date, None (célula vazia) ou INVALIDA."""
    if valor is None:
        return None
    if isinstance(valor, datetime):
        return valor.date()
    casamento = re.fullmatch(r"(\d{2})/(\d{2})/(\d{4})", str(valor).strip())
    if not casamento:
        return INVALIDA
    dia, mes, ano = (int(parte) for parte in casamento.groups())
    try:
        return date(ano, mes, dia)
    except ValueError:
        return INVALIDA


def somar_meses(inicio, meses):
    """Soma meses de calendário, como a função DATAM do Excel."""
    total = inicio.year * 12 + inicio.month - 1 + meses
    ano, mes = total // 12, total % 12 + 1
    return date(ano, mes, min(inicio.day, calendar.monthrange(ano, mes)[1]))


def funcionarios_unicos(controle):
    """Fica com a primeira linha de cada matrícula."""
    unicos = {}
    for linha in controle:
        unicos.setdefault(linha["Matrícula"], linha)
    return list(unicos.values())


def ativos(controle):
    return [
        linha for linha in funcionarios_unicos(controle)
        if limpar_texto(linha["Situação"]) == "Ativo"
    ]


def classificar(valor, regra, validade, data_ref):
    """Situação de um item, calculada de forma independente do gerador."""
    data = interpretar_data(valor)
    if data == INVALIDA:
        return "data_invalida"
    if data is None:
        return {
            "SIM": "faltando",
            "CONDICIONAL": "condicional_sem_data",
            "NÃO": "nao_aplicavel",
        }[regra]
    if validade == 0:
        return "sem_vencimento"
    dias = (somar_meses(data, validade) - data_ref).days
    if dias < 0:
        return "vencido"
    if dias <= 30:
        return "vence_ate_30"
    if dias <= 60:
        return "vence_31_a_60"
    if dias <= 90:
        return "vence_61_a_90"
    return "valido"
