from __future__ import annotations

import pytest

from apoio import CONTROLE, gerar_ok, ler_aba, ler_regras, ler_validades, limpar_texto


def pytest_addoption(parser):
    parser.addoption(
        "--desktop", action="store_true",
        help="roda também os testes que abrem o Power BI Desktop numa janela (marcados desktop)",
    )


def pytest_collection_modifyitems(config, items):
    if config.getoption("--desktop"):
        return
    pular = pytest.mark.skip(reason="abre o Power BI Desktop numa janela; rode com --desktop")
    for item in items:
        if "desktop" in item.keywords:
            item.add_marker(pular)


@pytest.fixture(scope="session")
def execucao(tmp_path_factory):
    """Uma geração com os valores padrão, compartilhada pelos testes de leitura."""
    pasta = tmp_path_factory.mktemp("padrao")
    resultado = gerar_ok(pasta)
    return pasta, resultado.stdout


@pytest.fixture(scope="session")
def pasta(execucao):
    return execucao[0]


@pytest.fixture(scope="session")
def resumo(execucao):
    return execucao[1]


@pytest.fixture(scope="session")
def controle(pasta):
    return ler_aba(pasta / CONTROLE, "Controle")


@pytest.fixture(scope="session")
def historico(pasta):
    return ler_aba(pasta / CONTROLE, "Historico")


@pytest.fixture(scope="session")
def validades(pasta):
    return ler_validades(pasta)


@pytest.fixture(scope="session")
def regras(pasta):
    return ler_regras(pasta)


@pytest.fixture(scope="session")
def regra_de(regras):
    """Regra de um treinamento para a função de uma linha da planilha bagunçada."""
    def buscar(linha, treinamento):
        return regras[limpar_texto(linha["Função"])][treinamento]
    return buscar
