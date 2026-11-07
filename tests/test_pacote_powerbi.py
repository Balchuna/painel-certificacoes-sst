"""O pacote do Power BI está completo e coerente entre as suas partes.

Não precisa do Excel: lê os arquivos como texto. Quem confere os números é
test_powerbi.py, que monta o pacote dentro do Excel.
"""
from __future__ import annotations

import json
import re

import pytest

from modelo_excel import MEDIDAS, MODELO, POWERQUERY, RAIZ, bloco_define, consultas, medidas, relacionamentos

MONTAGEM = RAIZ / "docs" / "MONTAGEM.md"
TEMA = RAIZ / "tema" / "tema.json"

# As medidas que a fase 3 do spec pede pelo nome.
MEDIDAS_DO_SPEC = [
    "Funcionários Ativos",
    "Itens Obrigatórios",
    "Itens Válidos",
    "% Conformidade",
    "Vencidos",
    "Vencem em 30 dias",
    "Vencem em 60 dias",
    "Vencem em 90 dias",
    "Pendentes Obrigatórios",
    "Dias para Vencer",
    "Status Farol",
]
# A tabela de cada consulta carregada aparece em MODELO.md como ### `nome`.
TABELA_NO_MODELO = re.compile(r"^###\s+`(\w+)`", re.M)
# Referência a medida: [Nome] sem tabela na frente.
USO_DE_MEDIDA = re.compile(r"(?<![\w'\]])\[([^\]]+)\]")
COR = re.compile(r'"(#[0-9A-Fa-f]{6})"')


def carregadas() -> set[str]:
    return {nome for nome, (_, carrega) in consultas().items() if carrega}


def test_cada_consulta_diz_se_carrega_no_modelo():
    pacote = consultas()  # levanta erro se algum .m não disser
    assert len(pacote) == len(list(POWERQUERY.glob("*.m"))) > 0


def test_tabelas_do_modelo_sao_as_consultas_carregadas():
    no_documento = set(TABELA_NO_MODELO.findall(MODELO.read_text(encoding="utf-8")))
    assert no_documento == carregadas()


def test_relacionamentos_ligam_colunas_que_as_consultas_criam():
    pacote = consultas()
    ligacoes = relacionamentos()
    assert len(ligacoes) == 7
    for lado in (lado for ligacao in ligacoes for lado in ligacao):
        tabela, coluna = lado
        assert tabela in carregadas(), lado
        assert f'"{coluna}"' in pacote[tabela][0], lado


def test_medidas_do_spec_estao_definidas():
    definidas = medidas()
    assert len(definidas) == len(set(definidas)), "medida definida duas vezes"
    assert set(MEDIDAS_DO_SPEC) <= set(definidas)


def test_toda_medida_usada_esta_definida():
    usadas = set(USO_DE_MEDIDA.findall(bloco_define()))
    assert usadas <= set(medidas()), usadas - set(medidas())


def test_medidas_ficam_na_tabela_medidas():
    assert "Medidas" in carregadas()
    texto = MEDIDAS.read_text(encoding="utf-8")
    assert re.findall(r"^\s*MEASURE\s+(\w+)\[", texto, re.M) == ["Medidas"] * len(medidas())


def test_tema_tem_as_cores_do_farol():
    tema = json.loads(TEMA.read_text(encoding="utf-8"))
    assert tema["name"]
    cores_do_tema = {cor.upper() for cor in tema["dataColors"]}
    cores_do_farol = {cor.upper() for cor in COR.findall(bloco_define())}
    assert len(cores_do_farol) == 9
    assert cores_do_farol <= cores_do_tema
    for chave in ("good", "neutral", "bad", "background", "foreground"):
        assert re.fullmatch(r"#[0-9A-Fa-f]{6}", tema[chave]), chave


@pytest.mark.parametrize("parte", ["consultas", "medidas"])
def test_passo_a_passo_cita_cada_parte(parte):
    texto = MONTAGEM.read_text(encoding="utf-8")
    nomes = consultas() if parte == "consultas" else medidas()
    faltando = [nome for nome in nomes if nome not in texto]
    assert not faltando


def test_passo_a_passo_tem_as_quatro_paginas():
    texto = MONTAGEM.read_text(encoding="utf-8")
    for pagina in ("Visão geral", "Matriz farol", "Agenda de reciclagem", "Qualidade dos dados"):
        assert re.search(rf"^#+ .*{pagina}", texto, re.M | re.I), pagina


def test_pacote_nao_traz_caminho_do_computador_de_ninguem():
    arquivos = [*POWERQUERY.glob("*.m"), MEDIDAS, MODELO, MONTAGEM, TEMA]
    for arquivo in arquivos:
        assert not re.search(r"[A-Za-z]:\\Users\\", arquivo.read_text(encoding="utf-8")), arquivo.name
