"""O gabarito do SQL contra um cálculo independente em pandas.

O gabarito é o que o Power BI precisa bater. O pandas parte da planilha bruta;
o SQL parte da versão limpa. Os dois têm de dar os mesmos números.
"""
import sqlite3

import pandas as pd
import pytest
from pandas.testing import assert_frame_equal

from apoio import (
    ENTRADA_VERSIONADA,
    GABARITO_VERSIONADO,
    LIMPA_VERSIONADA,
    RAIZ,
    SCRIPT_GABARITO,
    SCRIPT_LIMPEZA,
    gerar_ok,
    ler_csv,
    rodar_ok,
    rodar_script,
)
from calculo_pandas import calcular

CONSULTAS = [
    "01_visao_geral",
    "02_irregulares_hoje",
    "03_vencimentos_30_60_90",
    "04_agenda_reciclagem",
    "05_pendencias_por_funcao",
    "06_pendencias_por_treinamento",
]


def gerar_gabarito(limpa, pasta):
    rodar_ok(
        SCRIPT_GABARITO, "--limpa", limpa,
        "--banco", pasta / "painel.sqlite", "--gabarito", pasta / "gabarito",
    )
    return pasta / "gabarito"


def comparar(caminho, esperado):
    obtido = pd.read_csv(caminho, keep_default_na=False)
    # Percentuais saem do SQL com uma casa; o pandas guarda o valor exato.
    assert_frame_equal(
        obtido.reset_index(drop=True),
        esperado.reset_index(drop=True),
        check_dtype=False,
        check_exact=False,
        atol=0.0501,
        rtol=0,
    )


@pytest.fixture(scope="module")
def pasta(tmp_path_factory):
    pasta = tmp_path_factory.mktemp("gabarito")
    gerar_gabarito(LIMPA_VERSIONADA, pasta)
    return pasta


@pytest.fixture(scope="module")
def gabarito(pasta):
    return {consulta: ler_csv(pasta / "gabarito" / f"{consulta}.csv") for consulta in CONSULTAS}


@pytest.fixture(scope="module")
def calculado():
    return calcular(ENTRADA_VERSIONADA)


def test_uma_resposta_por_consulta(pasta):
    consultas = sorted(arquivo.stem for arquivo in (RAIZ / "sql" / "consultas").glob("*.sql"))
    assert consultas == CONSULTAS
    assert sorted(arquivo.stem for arquivo in (pasta / "gabarito").iterdir()) == CONSULTAS


@pytest.mark.parametrize("consulta", CONSULTAS)
def test_gabarito_bate_com_o_calculo_em_pandas(pasta, calculado, consulta):
    comparar(pasta / "gabarito" / f"{consulta}.csv", calculado[consulta])


def test_gabarito_versionado_igual_a_nova_execucao(gabarito):
    assert sorted(arquivo.stem for arquivo in GABARITO_VERSIONADO.iterdir()) == CONSULTAS
    for consulta in CONSULTAS:
        assert ler_csv(GABARITO_VERSIONADO / f"{consulta}.csv") == gabarito[consulta], consulta


def test_consultas_concordam_entre_si(gabarito):
    visao = gabarito["01_visao_geral"][0]
    pendentes = int(visao["pendentes_obrigatorios"])
    assert pendentes == int(visao["obrigatorios_sem_registro"]) + int(visao["obrigatorios_vencidos"])
    assert pendentes == sum(int(linha["pendencias"]) for linha in gabarito["02_irregulares_hoje"])
    assert pendentes == sum(int(linha["pendentes"]) for linha in gabarito["05_pendencias_por_funcao"])
    assert pendentes == sum(int(linha["pendentes"]) for linha in gabarito["06_pendencias_por_treinamento"])
    assert int(visao["funcionarios_irregulares"]) == len(gabarito["02_irregulares_hoje"])
    assert int(visao["funcionarios_ativos"]) == sum(
        int(linha["funcionarios_ativos"]) for linha in gabarito["05_pendencias_por_funcao"]
    )
    noventa = gabarito["03_vencimentos_30_60_90"][-1]
    assert noventa["janela_dias"] == "90"
    assert int(noventa["itens"]) == len(gabarito["04_agenda_reciclagem"])


def test_janelas_sao_cumulativas(gabarito):
    janelas = gabarito["03_vencimentos_30_60_90"]
    assert [linha["janela_dias"] for linha in janelas] == ["30", "60", "90"]
    itens = [int(linha["itens"]) for linha in janelas]
    assert itens == sorted(itens)


def test_banco_fica_pronto_para_consulta(pasta):
    banco = sqlite3.connect(pasta / "painel.sqlite")
    try:
        assert banco.execute("SELECT COUNT(*) FROM vw_status_item").fetchone() == (138 * 12,)
        assert banco.execute("SELECT COUNT(*) FROM qualidade_rejeicoes").fetchone() == (2,)
    finally:
        banco.close()


def test_outra_semente_e_outra_data_tambem_batem(tmp_path):
    # Prova que o acordo não depende dos dados publicados nem da data padrão.
    entrada, limpa = tmp_path / "entrada", tmp_path / "limpa"
    gerar_ok(entrada, "--semente", "7", "--data-referencia", "2026-06-01")
    rodar_ok(SCRIPT_LIMPEZA, "--entrada", entrada, "--saida", limpa)
    pasta = gerar_gabarito(limpa, tmp_path)
    calculado = calcular(entrada)
    assert ler_csv(pasta / "01_visao_geral.csv")[0]["data_referencia"] == "2026-06-01"
    for consulta in CONSULTAS:
        comparar(pasta / f"{consulta}.csv", calculado[consulta])


def test_csv_que_quebra_uma_regra_para_a_carga(tmp_path):
    limpa = tmp_path / "limpa"
    limpa.mkdir()
    for arquivo in LIMPA_VERSIONADA.iterdir():
        (limpa / arquivo.name).write_bytes(arquivo.read_bytes())
    fato = limpa / "fato_certificacao.csv"
    fato.write_text(fato.read_text(encoding="utf-8") + "9999,ASO,2026-01-10,Controle\n", encoding="utf-8")
    resultado = rodar_script(
        SCRIPT_GABARITO, "--limpa", limpa,
        "--banco", tmp_path / "painel.sqlite", "--gabarito", tmp_path / "gabarito",
    )
    assert resultado.returncode != 0
    assert "fato_certificacao.csv" in resultado.stderr
    assert "Traceback" not in resultado.stderr
    # Nem gabarito nem banco pela metade com cara de pronto.
    assert not (tmp_path / "gabarito").exists()
    assert not (tmp_path / "painel.sqlite").exists()
