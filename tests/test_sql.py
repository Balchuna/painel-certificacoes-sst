"""As tabelas e as views do SQL de referência, com dados montados à mão.

Cada teste monta um banco pequeno em memória com o caso que quer provar.
"""
import sqlite3
from datetime import date, timedelta

import pytest

from apoio import RAIZ, somar_meses

SQL = RAIZ / "sql"
REFERENCIA = date(2026, 11, 1)

# Um treinamento de cada tipo de regra, para a função FUNÇÃO X.
TREINAMENTOS = [
    ("A12", "Anual obrigatório", 12, "SIM"),
    ("C12", "Anual condicional", 12, "CONDICIONAL"),
    ("N12", "Anual que não se aplica", 12, "NÃO"),
    ("S00", "Obrigatório sem vencimento", 0, "SIM"),
]
FUNCAO = "FUNÇÃO X"


def montar_banco(janelas=(30, 60, 90), treinamentos=TREINAMENTOS):
    banco = sqlite3.connect(":memory:")
    banco.execute("PRAGMA foreign_keys = ON")
    banco.executescript((SQL / "01_tabelas.sql").read_text(encoding="utf-8"))
    banco.executescript((SQL / "02_views.sql").read_text(encoding="utf-8"))
    banco.execute(
        "INSERT INTO parametro (data_referencia, janela_1, janela_2, janela_3) VALUES (?, ?, ?, ?)",
        (REFERENCIA.isoformat(), *janelas),
    )
    banco.execute("INSERT INTO dim_funcao (funcao) VALUES (?)", (FUNCAO,))
    for codigo, nome, validade, regra in treinamentos:
        banco.execute(
            "INSERT INTO dim_treinamento (codigo, nome, validade_meses) VALUES (?, ?, ?)",
            (codigo, nome, validade),
        )
        banco.execute(
            "INSERT INTO regra_funcao_treinamento (funcao, treinamento, regra) VALUES (?, ?, ?)",
            (FUNCAO, codigo, regra),
        )
    return banco


def contratar(banco, matricula, situacao="Ativo"):
    banco.execute(
        "INSERT INTO dim_funcionario "
        "(matricula, nome, funcao, equipe, admissao, situacao, desligamento) "
        "VALUES (?, ?, ?, 'Equipe Teste', '2023-01-02', ?, ?)",
        (matricula, f"Pessoa {matricula}", FUNCAO, situacao,
         "2026-06-30" if situacao == "Desligado" else None),
    )


def emitir(banco, matricula, treinamento, data_emissao, origem="Controle"):
    banco.execute(
        "INSERT INTO fato_certificacao (matricula, treinamento, data_emissao, origem) "
        "VALUES (?, ?, ?, ?)",
        (matricula, treinamento, str(data_emissao), origem),
    )


def emissao_que_vence_em(dias, validade=12):
    """Data de emissão cujo vencimento cai `dias` depois da referência."""
    vencimento = REFERENCIA + timedelta(days=dias)
    emissao = somar_meses(vencimento, -validade)
    assert somar_meses(emissao, validade) == vencimento
    return emissao


def item(banco, matricula, treinamento):
    banco.row_factory = sqlite3.Row
    linha = banco.execute(
        "SELECT * FROM vw_status_item WHERE matricula = ? AND treinamento = ?",
        (matricula, treinamento),
    ).fetchone()
    assert linha is not None, (matricula, treinamento)
    return dict(linha)


@pytest.mark.parametrize(
    ("emissao", "meses", "vencimento"),
    [
        ("2024-03-15", 12, "2025-03-15"),
        ("2024-02-29", 12, "2025-02-28"),
        ("2024-01-31", 1, "2024-02-29"),
        ("2024-03-31", 1, "2024-04-30"),
        ("2023-12-31", 2, "2024-02-29"),
        ("2024-08-31", 6, "2025-02-28"),
    ],
)
def test_vencimento_soma_meses_como_o_excel(emissao, meses, vencimento):
    # O SQLite sozinho daria 2025-03-01 para 2024-02-29 + 12 meses.
    # O Excel (DATAM) e o Power BI (EDATE) param no último dia do mês.
    banco = montar_banco(treinamentos=[("T", "Teste", meses, "SIM")])
    contratar(banco, 1)
    emitir(banco, 1, "T", emissao)
    assert banco.execute(
        "SELECT data_vencimento FROM vw_registro_vigente WHERE matricula = 1"
    ).fetchone() == (vencimento,)


def test_vigente_e_a_emissao_mais_recente():
    banco = montar_banco()
    contratar(banco, 1)
    for data, origem in [("2024-01-10", "Historico"), ("2025-06-01", "Controle"),
                         ("2023-05-05", "Historico")]:
        emitir(banco, 1, "A12", data, origem)
    assert banco.execute(
        "SELECT data_emissao, emissoes, data_vencimento FROM vw_registro_vigente "
        "WHERE matricula = 1 AND treinamento = 'A12'"
    ).fetchall() == [("2025-06-01", 3, "2026-06-01")]


@pytest.mark.parametrize(
    ("dias", "status"),
    [
        (-400, "Vencido"),
        (-1, "Vencido"),
        (0, "Vence em até 30 dias"),
        (30, "Vence em até 30 dias"),
        (31, "Vence em 31 a 60 dias"),
        (60, "Vence em 31 a 60 dias"),
        (61, "Vence em 61 a 90 dias"),
        (90, "Vence em 61 a 90 dias"),
        (91, "Válido"),
    ],
)
def test_status_nas_fronteiras_das_janelas(dias, status):
    # Vencer na própria data de referência ainda vale: vence hoje, não venceu.
    banco = montar_banco()
    contratar(banco, 1)
    emitir(banco, 1, "A12", emissao_que_vence_em(dias))
    resultado = item(banco, 1, "A12")
    assert (resultado["dias_para_vencer"], resultado["status"]) == (dias, status)
    assert resultado["pendente"] == (1 if status == "Vencido" else 0)


def test_janelas_vem_dos_parametros():
    banco = montar_banco(janelas=(10, 20, 40))
    esperado = {5: "Vence em até 10 dias", 15: "Vence em 11 a 20 dias",
                40: "Vence em 21 a 40 dias", 41: "Válido"}
    for matricula, dias in enumerate(esperado, start=1):
        contratar(banco, matricula)
        emitir(banco, matricula, "A12", emissao_que_vence_em(dias))
    for matricula, (dias, status) in enumerate(esperado.items(), start=1):
        assert item(banco, matricula, "A12")["status"] == status, dias


def test_sem_registro_conforme_a_regra():
    banco = montar_banco()
    contratar(banco, 1)
    obtido = {
        codigo: (linha["status"], linha["obrigatorio"], linha["pendente"])
        for codigo in ("A12", "C12", "N12", "S00")
        for linha in [item(banco, 1, codigo)]
    }
    assert obtido == {
        "A12": ("Sem registro", 1, 1),
        "C12": ("Condicional sem registro", 0, 0),
        "N12": ("Não aplicável", 0, 0),
        "S00": ("Sem registro", 1, 1),
    }


def test_treinamento_sem_validade_nao_vence():
    banco = montar_banco()
    contratar(banco, 1)
    emitir(banco, 1, "S00", "2023-01-05")
    resultado = item(banco, 1, "S00")
    assert (resultado["data_vencimento"], resultado["dias_para_vencer"]) == (None, None)
    assert (resultado["status"], resultado["pendente"]) == ("Sem vencimento", 0)


def test_condicional_com_data_segue_o_vencimento_mas_nao_pende():
    banco = montar_banco()
    contratar(banco, 1)
    emitir(banco, 1, "C12", emissao_que_vence_em(-10))
    resultado = item(banco, 1, "C12")
    assert (resultado["status"], resultado["obrigatorio"], resultado["pendente"]) == ("Vencido", 0, 0)


def test_nao_aplicavel_mesmo_com_data():
    banco = montar_banco()
    contratar(banco, 1)
    emitir(banco, 1, "N12", emissao_que_vence_em(-10))
    resultado = item(banco, 1, "N12")
    assert (resultado["status"], resultado["pendente"]) == ("Não aplicável", 0)


def test_um_item_por_treinamento_de_cada_ativo():
    banco = montar_banco()
    contratar(banco, 1)
    contratar(banco, 2)
    emitir(banco, 1, "A12", "2025-01-10", "Historico")
    emitir(banco, 1, "A12", "2026-01-10")
    assert banco.execute(
        "SELECT matricula, COUNT(*) FROM vw_status_item GROUP BY matricula ORDER BY matricula"
    ).fetchall() == [(1, 4), (2, 4)]


def test_desligado_fica_fora():
    banco = montar_banco()
    contratar(banco, 1)
    contratar(banco, 2, situacao="Desligado")
    assert banco.execute("SELECT DISTINCT matricula FROM vw_status_item").fetchall() == [(1,)]
    assert banco.execute(
        "SELECT DISTINCT matricula FROM vw_pendencias_obrigatorias"
    ).fetchall() == [(1,)]


def test_pendencias_so_dos_itens_obrigatorios():
    banco = montar_banco()
    contratar(banco, 1)
    emitir(banco, 1, "A12", emissao_que_vence_em(-1))
    emitir(banco, 1, "C12", emissao_que_vence_em(-1))
    emitir(banco, 1, "N12", emissao_que_vence_em(-1))
    assert banco.execute(
        "SELECT treinamento, motivo FROM vw_pendencias_obrigatorias ORDER BY treinamento"
    ).fetchall() == [("A12", "Vencido"), ("S00", "Sem registro")]


def test_emissao_de_matricula_sem_cadastro_e_recusada():
    banco = montar_banco()
    with pytest.raises(sqlite3.IntegrityError):
        emitir(banco, 99, "A12", "2026-01-10")


def test_funcionario_de_funcao_sem_regra_e_recusado():
    banco = montar_banco()
    with pytest.raises(sqlite3.IntegrityError):
        banco.execute(
            "INSERT INTO dim_funcionario (matricula, nome, funcao, equipe, admissao, situacao) "
            "VALUES (1, 'Pessoa', 'FUNÇÃO SEM REGRA', 'Equipe', '2023-01-02', 'Ativo')"
        )


@pytest.mark.parametrize(
    ("tabela", "colunas", "valores"),
    [
        ("regra_funcao_treinamento", "funcao, treinamento, regra", (FUNCAO, "A12", "TALVEZ")),
        ("fato_certificacao", "matricula, treinamento, data_emissao, origem", (1, "A12", "10/01/2026", "Controle")),
        ("dim_treinamento", "codigo, nome, validade_meses", ("X", "Negativo", -1)),
    ],
)
def test_valores_fora_do_formato_sao_recusados(tabela, colunas, valores):
    banco = montar_banco()
    contratar(banco, 1)
    if tabela == "regra_funcao_treinamento":
        banco.execute("DELETE FROM regra_funcao_treinamento WHERE treinamento = 'A12'")
    marcadores = ", ".join("?" * len(valores))
    with pytest.raises(sqlite3.IntegrityError):
        banco.execute(f"INSERT INTO {tabela} ({colunas}) VALUES ({marcadores})", valores)


def test_janelas_precisam_crescer():
    with pytest.raises(sqlite3.IntegrityError):
        montar_banco(janelas=(60, 30, 90))
