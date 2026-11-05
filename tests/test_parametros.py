"""As regras precisam estar completas e limpas: é por elas que tudo se liga."""
from __future__ import annotations

import pytest

from apoio import CONTROLE, FUNCOES, PARAMETROS, TREINAMENTOS, ler_aba
from openpyxl import load_workbook


def test_todo_treinamento_tem_validade(validades):
    """Quebra se faltar um treinamento ou sobrar um código desconhecido."""
    assert set(validades) == set(TREINAMENTOS)


@pytest.mark.parametrize("treinamento, meses", [
    ("ASO", 12), ("NR01", 0), ("NR05", 0), ("NR06", 0), ("NR12", 0), ("NR18", 24),
    ("NR34", 0), ("NR35", 24), ("PEMT1", 24), ("PEMT2", 24), ("ANDAIME", 0), ("CARTEIRA", 0),
])
def test_validade_segue_a_config_sst(validades, treinamento, meses):
    """Quebra se uma validade for digitada errada: todo vencimento depende dela."""
    assert validades[treinamento] == meses


def test_matriz_de_regras_esta_completa(regras):
    """Quebra se uma combinação de função e treinamento ficar sem regra."""
    assert set(regras) == FUNCOES
    for funcao, por_treinamento in regras.items():
        assert list(por_treinamento) == TREINAMENTOS, funcao


def test_regras_usam_so_os_tres_valores_e_todos_aparecem(regras):
    """Quebra se aparecer outro valor, ou se um dos três nunca for exercitado."""
    usados = {valor for por_treinamento in regras.values() for valor in por_treinamento.values()}

    assert usados == {"SIM", "NÃO", "CONDICIONAL"}


@pytest.mark.parametrize("treinamento", ["ASO", "NR01", "NR06", "NR18"])
def test_itens_basicos_sao_obrigatorios_para_todas_as_funcoes(regras, treinamento):
    """Quebra se um item que a Config_SST exige de todos deixar de ser obrigatório."""
    assert {por_treinamento[treinamento] for por_treinamento in regras.values()} == {"SIM"}


def test_parametros_nao_tem_espacos_sobrando(regras, validades):
    """Quebra se a bagunça vazar para a planilha de regras, que é a chave de ligação."""
    for texto in [*regras, *validades]:
        assert texto == " ".join(texto.split())


@pytest.mark.parametrize("parametro, valor", [
    ("Janela de alerta 1 (dias)", 30),
    ("Janela de alerta 2 (dias)", 60),
    ("Janela de alerta 3 (dias)", 90),
])
def test_janelas_de_alerta_estao_nos_parametros(pasta, parametro, valor):
    """Quebra se as janelas da pergunta de negócio ficarem fora dos parâmetros."""
    alertas = ler_aba(pasta / PARAMETROS, "Alertas")

    assert next(l["Valor"] for l in alertas if l["Parâmetro"] == parametro) == valor


@pytest.mark.parametrize("arquivo", [CONTROLE, PARAMETROS])
def test_toda_planilha_avisa_que_os_dados_sao_sinteticos(pasta, arquivo):
    """Quebra se um arquivo circular sozinho sem dizer que é fictício."""
    planilha = load_workbook(pasta / arquivo, read_only=True)
    try:
        texto = " ".join(
            str(valor)
            for linha in planilha["Leia-me"].iter_rows(values_only=True)
            for valor in linha if valor
        )
    finally:
        planilha.close()

    assert "sintéticos" in texto.lower()
