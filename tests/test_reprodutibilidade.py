"""A mesma semente e a mesma data precisam gerar sempre os mesmos arquivos."""
from __future__ import annotations

import time
from datetime import date

import pytest

from apoio import (
    COLUNAS_DATA,
    CONTROLE,
    ENTRADA_VERSIONADA,
    INVALIDA,
    PARAMETROS,
    gerar_ok,
    interpretar_data,
    ler_aba,
    ler_todas_as_celulas,
    rodar_gerador,
)


@pytest.mark.parametrize("arquivo", [CONTROLE, PARAMETROS])
def test_duas_execucoes_geram_exatamente_os_mesmos_bytes(tmp_path, arquivo):
    """Quebra se o gerador usar o relógio, ordem de set ou sorteio sem semente.

    A espera de mais de 2 segundos é de propósito: o zip guarda a hora com
    resolução de 2 segundos, e sem ela um carimbo de hora passaria despercebido.
    As sementes de hash diferentes expõem qualquer dependência da ordem de set.
    """
    gerar_ok(tmp_path / "a", hash_seed="1")
    time.sleep(2.1)
    gerar_ok(tmp_path / "b", hash_seed="2")

    assert (tmp_path / "a" / arquivo).read_bytes() == (tmp_path / "b" / arquivo).read_bytes()


def test_semente_diferente_gera_outros_dados(tmp_path):
    """Quebra se a semente for ignorada."""
    gerar_ok(tmp_path / "a", "--semente", "1")
    gerar_ok(tmp_path / "b", "--semente", "2")

    assert ler_aba(tmp_path / "a" / CONTROLE, "Controle") != ler_aba(tmp_path / "b" / CONTROLE, "Controle")


@pytest.mark.parametrize("texto, data_ref", [
    ("2026-06-01", date(2026, 6, 1)),
    ("2027-03-15", date(2027, 3, 15)),
])
def test_data_de_referencia_e_respeitada(tmp_path, texto, data_ref):
    """Quebra se a data for fixa no código ou se surgir data depois dela."""
    gerar_ok(tmp_path, "--data-referencia", texto)

    alertas = ler_aba(tmp_path / PARAMETROS, "Alertas")
    registrada = next(l["Valor"] for l in alertas if l["Parâmetro"] == "Data de referência")
    assert registrada.date() == data_ref

    controle = ler_aba(tmp_path / CONTROLE, "Controle")
    datas = [interpretar_data(linha[c]) for linha in controle for c in COLUNAS_DATA]
    datas = [d for d in datas if d is not None and d != INVALIDA]
    assert max(datas) <= data_ref

    historico = ler_aba(tmp_path / CONTROLE, "Historico")
    assert max(linha["Data de emissão"].date() for linha in historico) <= data_ref


def test_data_de_referencia_depois_de_2026_nao_cria_admissao_em_2027(tmp_path):
    """Quebra se a janela de admissões acompanhar a data de referência sem limite."""
    gerar_ok(tmp_path, "--data-referencia", "2027-03-15")

    controle = ler_aba(tmp_path / CONTROLE, "Controle")
    assert max(interpretar_data(l["Admissão"]) for l in controle).year == 2026


@pytest.mark.parametrize("texto", ["01/11/2026", "2026-13-40", "ontem"])
def test_data_de_referencia_mal_escrita_e_recusada(tmp_path, texto):
    """Quebra se uma data errada virar traceback ou arquivo gerado."""
    resultado = rodar_gerador(tmp_path, "--data-referencia", texto)

    assert resultado.returncode != 0
    assert "--data-referencia" in resultado.stderr
    assert "Traceback" not in resultado.stderr
    assert not (tmp_path / CONTROLE).exists()


def test_data_de_referencia_anterior_as_admissoes_e_recusada(tmp_path):
    """Quebra se o gerador tentar sortear admissões numa janela vazia."""
    resultado = rodar_gerador(tmp_path, "--data-referencia", "2022-06-01")

    assert resultado.returncode != 0
    assert "--data-referencia" in resultado.stderr
    assert "Traceback" not in resultado.stderr
    assert not (tmp_path / CONTROLE).exists()


@pytest.mark.parametrize("arquivo", [CONTROLE, PARAMETROS])
def test_arquivos_versionados_batem_com_uma_nova_geracao(tmp_path, arquivo):
    """Quebra se alguém mudar o gerador e esquecer de regenerar data/entrada.

    Compara célula a célula, e não byte a byte, porque a compactação do zip
    pode variar entre sistemas operacionais sem mudar nenhum dado.
    """
    gerar_ok(tmp_path)

    assert ler_todas_as_celulas(ENTRADA_VERSIONADA / arquivo) == ler_todas_as_celulas(tmp_path / arquivo)
