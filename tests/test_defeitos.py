"""Os defeitos que o spec pede precisam existir na planilha, na medida certa."""
from __future__ import annotations

import re
from collections import Counter
from datetime import datetime

import pytest

from openpyxl import load_workbook

from apoio import (
    COLUNAS_CADASTRO,
    COLUNAS_DATA,
    CONTROLE,
    FUNCOES,
    INVALIDA,
    TREINAMENTOS,
    gerar_ok,
    interpretar_data,
    ler_aba,
    limpar_texto,
)


def eh_data_em_texto(valor):
    return isinstance(valor, str) and interpretar_data(valor) != INVALIDA


def celulas_invalidas(controle):
    return [
        (linha, coluna)
        for linha in controle
        for coluna in COLUNAS_DATA
        if interpretar_data(linha[coluna]) == INVALIDA
    ]


def test_ha_uma_coluna_por_treinamento(controle):
    """Quebra se a planilha deixar de ser larga ou faltar um treinamento."""
    assert list(controle[0]) == COLUNAS_CADASTRO + TREINAMENTOS


def test_colunas_de_data_cabem_na_tela_do_excel(pasta):
    """Quebra se o Excel mostrar ######## no lugar das datas, por coluna estreita."""
    planilha = load_workbook(pasta / CONTROLE)
    try:
        aba = planilha["Controle"]
        cabecalho = [celula.value for celula in aba[1]]
        # Só conta a largura gravada no arquivo. Perguntar pela letra da coluna não
        # serviria: o openpyxl responde 13 mesmo quando nada foi gravado, e o Excel
        # usaria a largura padrão dele, estreita demais para dd/mm/aaaa em Arial 10.
        gravadas = {
            indice: dimensao.width
            for dimensao in aba.column_dimensions.values()
            for indice in range(dimensao.min, dimensao.max + 1)
        }
        for coluna in COLUNAS_DATA:
            assert gravadas.get(cabecalho.index(coluna) + 1, 0) >= 12, coluna
    finally:
        planilha.close()


@pytest.mark.parametrize("semente, data_ref", [
    ("1", "2024-02-01"),
    ("2", "2025-07-15"),
    ("3", "2027-03-15"),
])
def test_defeitos_valem_para_outras_sementes_e_datas(tmp_path, semente, data_ref):
    """Quebra se os defeitos só existirem por sorte da semente padrão."""
    gerar_ok(tmp_path, "--semente", semente, "--data-referencia", data_ref)
    controle = ler_aba(tmp_path / CONTROLE, "Controle")

    assert len(celulas_invalidas(controle)) == 1
    assert sorted(n for n in Counter(l["Matrícula"] for l in controle).values() if n > 1) == [2]
    assert any(eh_data_em_texto(l[c]) for l in controle for c in COLUNAS_DATA)
    assert any(l["Nome"] != l["Nome"].strip() for l in controle)


def test_datas_vem_como_texto_em_parte_das_linhas(controle):
    """Quebra se nenhuma, ou quase todas as linhas, trouxerem texto no lugar de data."""
    com_texto = [l for l in controle if any(eh_data_em_texto(l[c]) for c in COLUNAS_DATA)]

    assert 0.10 * len(controle) <= len(com_texto) <= 0.40 * len(controle)


def test_as_outras_linhas_trazem_datas_de_verdade(controle):
    """Quebra se o defeito de texto se espalhar para a planilha toda."""
    com_data_real = [
        l for l in controle
        if any(isinstance(l[c], datetime) for c in COLUNAS_DATA)
    ]

    assert len(com_data_real) >= 0.60 * len(controle)


def test_linha_com_data_em_texto_nao_mistura_com_data_de_verdade(controle):
    """Quebra se o defeito deixar de ser por linha, como o spec descreve."""
    for linha in controle:
        valores = [linha[c] for c in COLUNAS_DATA]
        assert not (any(map(eh_data_em_texto, valores)) and any(isinstance(v, datetime) for v in valores))


@pytest.mark.parametrize("coluna", ["Nome", "Função", "Equipe"])
def test_ha_espacos_sobrando_nas_pontas(controle, coluna):
    """Quebra se o texto sair limpo e o Power Query não tiver o que aparar."""
    sujos = [l[coluna] for l in controle if l[coluna] != l[coluna].strip()]

    assert len(sujos) >= 5


def test_ha_nomes_com_espaco_repetido_no_meio(controle):
    """Quebra se só houver espaços nas pontas: aparar as pontas não resolveria."""
    assert any("  " in l["Nome"].strip() for l in controle)


def test_ha_datas_em_texto_com_espaco_sobrando(controle):
    """Quebra se a conversão de texto em data puder ignorar o aparo."""
    assert any(
        eh_data_em_texto(l[c]) and l[c] != l[c].strip()
        for l in controle for c in COLUNAS_DATA
    )


def test_limpar_os_espacos_recupera_cinco_funcoes_e_tres_equipes(controle):
    """Quebra se o defeito for além de espaços e mudar o nome da função ou da equipe."""
    assert {limpar_texto(l["Função"]) for l in controle} == FUNCOES
    assert len({limpar_texto(l["Equipe"]) for l in controle}) == 3


def test_exatamente_um_funcionario_aparece_duas_vezes(controle):
    """Quebra se o duplicado sumir ou se surgirem outros."""
    contagem = Counter(l["Matrícula"] for l in controle)

    assert sorted(n for n in contagem.values() if n > 1) == [2]


def test_linhas_duplicadas_so_diferem_antes_da_limpeza(controle):
    """Quebra se o duplicado for cópia exata ou se trouxer dados diferentes."""
    contagem = Counter(l["Matrícula"] for l in controle)
    matricula = next(m for m, n in contagem.items() if n == 2)
    primeira, segunda = [l for l in controle if l["Matrícula"] == matricula]

    assert primeira != segunda
    for coluna in COLUNAS_CADASTRO + TREINAMENTOS:
        if coluna in COLUNAS_DATA:
            assert interpretar_data(primeira[coluna]) == interpretar_data(segunda[coluna]), coluna
        else:
            assert limpar_texto(primeira[coluna]) == limpar_texto(segunda[coluna]), coluna


def test_linhas_duplicadas_nao_ficam_grudadas(controle):
    """Quebra se o duplicado ficar colado no original, fácil demais de achar a olho."""
    contagem = Counter(l["Matrícula"] for l in controle)
    matricula = next(m for m, n in contagem.items() if n == 2)
    posicoes = [i for i, l in enumerate(controle) if l["Matrícula"] == matricula]

    assert posicoes[1] - posicoes[0] >= 10


def test_exatamente_uma_data_invalida(controle):
    """Quebra se a data inválida sumir ou se surgir mais de uma."""
    assert len(celulas_invalidas(controle)) == 1


def test_data_invalida_parece_data_mas_nao_existe_no_calendario(controle):
    """Quebra se o defeito for um texto qualquer, que seria fácil de distinguir."""
    (linha, coluna), = celulas_invalidas(controle)

    assert re.fullmatch(r"\d{2}/\d{2}/\d{4}", linha[coluna])


def test_data_invalida_cai_em_item_obrigatorio_de_funcionario_ativo(controle, regra_de):
    """Quebra se a rejeição da célula não mudar nenhum número do painel."""
    (linha, coluna), = celulas_invalidas(controle)

    assert coluna in TREINAMENTOS
    assert regra_de(linha, coluna) == "SIM"
    assert limpar_texto(linha["Situação"]) == "Ativo"


def test_data_invalida_nao_cai_no_funcionario_duplicado(controle):
    """Quebra se o inválido virar dois, ou se as duas linhas duplicadas divergirem."""
    (linha, _), = celulas_invalidas(controle)

    assert sum(l["Matrícula"] == linha["Matrícula"] for l in controle) == 1


def test_item_com_data_invalida_nao_tem_emissao_anterior(controle, historico):
    """Quebra se o item rejeitado puder voltar a valer por uma emissão antiga.

    Sem histórico, a limpeza tem uma única resposta: o item fica sem registro.
    """
    (linha, coluna), = celulas_invalidas(controle)

    assert not [
        h for h in historico
        if h["Matrícula"] == linha["Matrícula"] and h["Treinamento"] == coluna
    ]
