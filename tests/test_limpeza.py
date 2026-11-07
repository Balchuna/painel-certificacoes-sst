"""A limpeza grava a versão limpa em CSV e registra o que descartou.

As expectativas saem da planilha bruta, lida pelo leitor próprio dos testes.
"""
import re

import pytest

from apoio import (
    COLUNAS_DATA,
    CONTROLE,
    ENTRADA_VERSIONADA,
    FUNCOES,
    INVALIDA,
    LIMPA_VERSIONADA,
    SCRIPT_LIMPEZA,
    TREINAMENTOS,
    funcionarios_unicos,
    interpretar_data,
    ler_aba,
    ler_csv,
    ler_regras,
    ler_validades,
    limpar_texto,
    rodar_ok,
    rodar_script,
)

ISO = re.compile(r"\d{4}-\d{2}-\d{2}")

ARQUIVOS = {
    "dim_funcionario.csv",
    "dim_funcao.csv",
    "dim_treinamento.csv",
    "regra_funcao_treinamento.csv",
    "fato_certificacao.csv",
    "parametro.csv",
    "qualidade_rejeicoes.csv",
}


@pytest.fixture(scope="module")
def limpa(tmp_path_factory):
    saida = tmp_path_factory.mktemp("limpa")
    rodar_ok(SCRIPT_LIMPEZA, "--entrada", ENTRADA_VERSIONADA, "--saida", saida)
    return saida


@pytest.fixture(scope="module")
def controle_bruto():
    return ler_aba(ENTRADA_VERSIONADA / CONTROLE, "Controle")


def iso_ou_vazio(valor):
    data = interpretar_data(valor)
    return "" if data is None else data.isoformat()


def rejeicoes_esperadas(controle):
    """Segunda linha de uma matrícula sai inteira; data inválida sai sozinha."""
    vistas = set()
    esperadas = []
    for numero, linha in enumerate(controle, start=2):
        matricula = str(linha["Matrícula"])
        if matricula in vistas:
            esperadas.append((
                "Controle", str(numero), matricula, "Matrícula", matricula,
                "Matrícula duplicada", "Linha descartada",
            ))
            continue
        vistas.add(matricula)
        for coluna in COLUNAS_DATA:
            if interpretar_data(linha[coluna]) == INVALIDA:
                esperadas.append((
                    "Controle", str(numero), matricula, coluna, str(linha[coluna]),
                    "Data inválida", "Célula descartada",
                ))
    return esperadas


def test_grava_os_sete_arquivos(limpa):
    assert {arquivo.name for arquivo in limpa.iterdir()} == ARQUIVOS


def test_um_cadastro_por_funcionario(limpa):
    matriculas = [linha["matricula"] for linha in ler_csv(limpa / "dim_funcionario.csv")]
    assert len(matriculas) == 150
    assert len(set(matriculas)) == 150


def test_textos_sem_espacos_sobrando(limpa):
    for linha in ler_csv(limpa / "dim_funcionario.csv"):
        for coluna in ("nome", "funcao", "equipe", "situacao"):
            assert linha[coluna], (linha["matricula"], coluna)
            assert linha[coluna] == limpar_texto(linha[coluna]), (linha["matricula"], coluna)


def test_cadastro_fica_com_a_primeira_linha_limpa(limpa, controle_bruto):
    esperado = [
        {
            "matricula": str(linha["Matrícula"]),
            "nome": limpar_texto(linha["Nome"]),
            "funcao": limpar_texto(linha["Função"]),
            "equipe": limpar_texto(linha["Equipe"]),
            "admissao": iso_ou_vazio(linha["Admissão"]),
            "situacao": limpar_texto(linha["Situação"]),
            "desligamento": iso_ou_vazio(linha["Desligamento"]),
        }
        for linha in funcionarios_unicos(controle_bruto)
    ]
    esperado.sort(key=lambda linha: int(linha["matricula"]))
    assert ler_csv(limpa / "dim_funcionario.csv") == esperado


def test_datas_em_iso(limpa):
    for linha in ler_csv(limpa / "dim_funcionario.csv"):
        assert ISO.fullmatch(linha["admissao"]), linha
        assert linha["desligamento"] == "" or ISO.fullmatch(linha["desligamento"]), linha
    for linha in ler_csv(limpa / "fato_certificacao.csv"):
        assert ISO.fullmatch(linha["data_emissao"]), linha


def test_rejeita_so_o_duplicado_e_a_data_invalida(limpa, controle_bruto):
    rejeicoes = [
        tuple(linha.values()) for linha in ler_csv(limpa / "qualidade_rejeicoes.csv")
    ]
    assert rejeicoes == rejeicoes_esperadas(controle_bruto)
    assert [r[5] for r in rejeicoes] == ["Matrícula duplicada", "Data inválida"]


def test_data_invalida_nao_vira_emissao(limpa):
    emissoes = {
        (linha["matricula"], linha["treinamento"])
        for linha in ler_csv(limpa / "fato_certificacao.csv")
    }
    for rejeicao in ler_csv(limpa / "qualidade_rejeicoes.csv"):
        if rejeicao["motivo"] == "Data inválida":
            assert (rejeicao["matricula"], rejeicao["coluna"]) not in emissoes


def test_emissoes_juntam_controle_e_historico(limpa, controle_bruto):
    esperado = set()
    for linha in funcionarios_unicos(controle_bruto):
        for codigo in TREINAMENTOS:
            data = interpretar_data(linha[codigo])
            if data not in (None, INVALIDA):
                esperado.add((str(linha["Matrícula"]), codigo, data.isoformat(), "Controle"))
    for linha in ler_aba(ENTRADA_VERSIONADA / CONTROLE, "Historico"):
        data = interpretar_data(linha["Data de emissão"])
        esperado.add((str(linha["Matrícula"]), linha["Treinamento"], data.isoformat(), "Historico"))

    emissoes = [tuple(linha.values()) for linha in ler_csv(limpa / "fato_certificacao.csv")]
    assert len(emissoes) == len(set(emissoes))
    assert set(emissoes) == esperado


def test_regras_despivotadas(limpa):
    regras = ler_regras(ENTRADA_VERSIONADA)
    esperado = [
        {"funcao": funcao, "treinamento": codigo, "regra": regra}
        for funcao, linha in regras.items()
        for codigo, regra in linha.items()
    ]
    assert len(esperado) == 60
    assert ler_csv(limpa / "regra_funcao_treinamento.csv") == esperado


def test_funcoes(limpa):
    assert {linha["funcao"] for linha in ler_csv(limpa / "dim_funcao.csv")} == FUNCOES


def test_treinamentos_com_validade(limpa):
    validades = ler_validades(ENTRADA_VERSIONADA)
    linhas = ler_csv(limpa / "dim_treinamento.csv")
    assert [linha["codigo"] for linha in linhas] == TREINAMENTOS
    assert {linha["codigo"]: int(linha["validade_meses"]) for linha in linhas} == validades


def test_parametros(limpa):
    assert ler_csv(limpa / "parametro.csv") == [
        {"data_referencia": "2026-11-01", "janela_1": "30", "janela_2": "60", "janela_3": "90"}
    ]


def test_duas_execucoes_dao_os_mesmos_bytes(limpa, tmp_path):
    rodar_ok(SCRIPT_LIMPEZA, "--entrada", ENTRADA_VERSIONADA, "--saida", tmp_path)
    for nome in ARQUIVOS:
        assert (tmp_path / nome).read_bytes() == (limpa / nome).read_bytes(), nome
        assert b"\r" not in (limpa / nome).read_bytes(), nome


def test_versao_limpa_versionada_igual_a_nova_execucao(limpa):
    # Compara o conteúdo: o git pode trocar o fim de linha no checkout.
    assert {arquivo.name for arquivo in LIMPA_VERSIONADA.iterdir()} == ARQUIVOS
    for nome in ARQUIVOS:
        assert ler_csv(LIMPA_VERSIONADA / nome) == ler_csv(limpa / nome), nome


def test_entrada_inexistente_explica_o_erro(tmp_path):
    resultado = rodar_script(
        SCRIPT_LIMPEZA, "--entrada", tmp_path / "nao-existe", "--saida", tmp_path / "saida"
    )
    assert resultado.returncode != 0
    assert "nao-existe" in resultado.stderr
    assert "Traceback" not in resultado.stderr
