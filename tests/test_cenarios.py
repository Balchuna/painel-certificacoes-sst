"""O conteúdo precisa cobrir os casos da pergunta de negócio e fazer sentido."""
from __future__ import annotations

import re
from collections import Counter, defaultdict
from datetime import date, timedelta

import pytest

from apoio import (
    CONTROLE,
    DATA_REF,
    FUNCOES,
    INVALIDA,
    TREINAMENTOS,
    ativos,
    classificar,
    funcionarios_unicos,
    gerar_ok,
    interpretar_data,
    ler_aba,
    ler_regras,
    ler_validades,
    limpar_texto,
    somar_meses,
)

AJUDANTE = "AJ. DE MONTADOR DE STEEL FRAME"


def pendencias_por(controle, regras, validades, agrupar_por):
    """{grupo: (pendentes, obrigatórios)} entre os itens SIM dos ativos.

    Pendente = obrigatório sem registro ou vencido na data de referência.
    """
    obrigatorios, pendentes = Counter(), Counter()
    for linha in ativos(controle):
        funcao = limpar_texto(linha["Função"])
        for treinamento in TREINAMENTOS:
            if regras[funcao][treinamento] != "SIM":
                continue
            situacao = classificar(linha[treinamento], "SIM", validades[treinamento], DATA_REF)
            grupo = funcao if agrupar_por == "função" else treinamento
            obrigatorios[grupo] += 1
            pendentes[grupo] += situacao in {"faltando", "vencido"}
    return {grupo: (pendentes[grupo], obrigatorios[grupo]) for grupo in obrigatorios}


def lider_e_folga(contagem):
    """Grupo com a maior taxa de pendência e quantas vezes ela supera a do resto somado."""
    taxa = {grupo: p / o for grupo, (p, o) in contagem.items()}
    lider = max(taxa, key=taxa.get)
    pendentes_resto = sum(p for grupo, (p, _) in contagem.items() if grupo != lider)
    obrigatorios_resto = sum(o for grupo, (_, o) in contagem.items() if grupo != lider)
    if pendentes_resto == 0:
        return lider, float("inf")
    return lider, taxa[lider] / (pendentes_resto / obrigatorios_resto)


@pytest.fixture(scope="module")
def situacoes(controle, regra_de, validades):
    """Situação de cada item (funcionário ativo x treinamento) na data de referência."""
    return [
        (linha, treinamento, classificar(linha[treinamento], regra_de(linha, treinamento),
                                         validades[treinamento], DATA_REF))
        for linha in ativos(controle)
        for treinamento in TREINAMENTOS
    ]


@pytest.fixture(scope="module")
def emissoes(controle, historico):
    """{(matrícula, treinamento): [datas em ordem]} juntando Historico e Controle."""
    resultado = defaultdict(list)
    for linha in historico:
        resultado[linha["Matrícula"], linha["Treinamento"]].append(linha["Data de emissão"].date())
    for linha in funcionarios_unicos(controle):
        for treinamento in TREINAMENTOS:
            data = interpretar_data(linha[treinamento])
            if data is not None and data != INVALIDA:
                resultado[linha["Matrícula"], treinamento].append(data)
    return dict(resultado)


# ---------- funcionários ----------

def test_sao_150_funcionarios_e_uma_linha_a_mais_do_duplicado(controle):
    """Quebra se o tamanho da obra ou o duplicado mudarem por acidente."""
    assert len(funcionarios_unicos(controle)) == 150
    assert len(controle) == 151


def test_cada_funcao_tem_gente_suficiente_para_comparar(controle):
    """Quebra se uma função ficar sem funcionários e sumir do painel."""
    por_funcao = Counter(limpar_texto(l["Função"]) for l in funcionarios_unicos(controle))

    assert set(por_funcao) == FUNCOES
    assert min(por_funcao.values()) >= 5


def test_cada_equipe_tem_gente_suficiente_para_comparar(controle):
    """Quebra se uma equipe ficar quase vazia."""
    por_equipe = Counter(limpar_texto(l["Equipe"]) for l in funcionarios_unicos(controle))

    assert len(por_equipe) == 3
    assert min(por_equipe.values()) >= 20


def test_admissoes_cobrem_de_2023_a_2026(controle):
    """Quebra se a janela de admissões sair do período que o spec pede."""
    anos = {interpretar_data(l["Admissão"]).year for l in controle}

    assert anos == {2023, 2024, 2025, 2026}


def test_nomes_sao_unicos(controle):
    """Quebra se dois funcionários diferentes puderem parecer o mesmo duplicado."""
    nomes = [limpar_texto(l["Nome"]) for l in funcionarios_unicos(controle)]

    assert len(set(nomes)) == 150


def test_nomes_de_exemplo_do_modelo_de_referencia_nao_foram_reaproveitados(controle):
    """Quebra se dados da planilha de referência entrarem no projeto."""
    usados_no_modelo = {
        "Carlos Eduardo Ramos", "Marina Souza Lima", "João Pedro Alves",
        "Fernanda Costa", "Roberto Nunes",
    }

    assert not usados_no_modelo & {limpar_texto(l["Nome"]) for l in controle}


def test_nenhuma_coluna_de_documento_pessoal(controle):
    """Quebra se alguém acrescentar CPF, RG ou parecido à planilha."""
    assert not [c for c in controle[0] if re.search(r"cpf|rg\b|pis|ctps|nascimento", c, re.I)]


def test_tem_desligados_mas_a_maioria_esta_ativa(controle):
    """Quebra se os desligados sumirem ou dominarem a obra."""
    desligados = 150 - len(ativos(controle))

    assert 5 <= desligados <= 30


def test_situacao_e_data_de_desligamento_andam_juntas(controle):
    """Quebra se houver ativo com data de desligamento, ou desligado sem ela."""
    for linha in controle:
        desligado = limpar_texto(linha["Situação"]) == "Desligado"
        assert (linha["Desligamento"] is not None) == desligado, linha["Matrícula"]


def test_desligamento_fica_entre_admissao_e_data_de_referencia(controle):
    """Quebra se houver saída antes da entrada ou no futuro."""
    for linha in controle:
        if linha["Desligamento"] is not None:
            saida = interpretar_data(linha["Desligamento"])
            assert interpretar_data(linha["Admissão"]) < saida <= DATA_REF, linha["Matrícula"]


# ---------- cenários que a pergunta de negócio precisa encontrar ----------

@pytest.mark.parametrize("situacao, minimo", [
    ("faltando", 5),
    ("vencido", 5),
    ("vence_ate_30", 3),
    ("vence_31_a_60", 3),
    ("vence_61_a_90", 3),
    ("valido", 20),
    ("sem_vencimento", 20),
    ("condicional_sem_data", 20),
    ("nao_aplicavel", 20),
])
def test_cada_situacao_existe_entre_os_ativos(situacoes, situacao, minimo):
    """Quebra se um caso que o painel precisa mostrar ficar vazio."""
    assert Counter(s for _, _, s in situacoes)[situacao] >= minimo


def test_condicional_aparece_com_data_e_sem_data(controle, regra_de):
    """Quebra se CONDICIONAL virar sinônimo de obrigatório ou de não aplicável."""
    condicionais = [
        interpretar_data(l[t]) is not None
        for l in funcionarios_unicos(controle)
        for t in TREINAMENTOS
        if regra_de(l, t) == "CONDICIONAL"
    ]

    assert any(condicionais) and not all(condicionais)


def test_regra_nao_nunca_tem_data(controle, regra_de):
    """Quebra se o gerador emitir treinamento que a regra diz não se aplicar."""
    for linha in funcionarios_unicos(controle):
        for treinamento in TREINAMENTOS:
            if regra_de(linha, treinamento) == "NÃO":
                assert linha[treinamento] is None, (linha["Matrícula"], treinamento)


def test_ajudantes_concentram_as_pendencias_com_folga(controle, regras, validades):
    """Quebra se "qual função concentra" perder a resposta clara descrita em DECISOES.md.

    A concentração é sintética, criada pelos fatores do gerador. Comparar o líder
    com a menor taxa não serviria: funções pequenas chegam a zero por acaso.
    """
    lider, folga = lider_e_folga(pendencias_por(controle, regras, validades, "função"))

    assert lider == AJUDANTE
    assert folga >= 1.5


@pytest.mark.parametrize("semente", ["1", "2", "3", "4", "5"])
def test_ajudantes_lideram_tambem_em_outras_sementes(tmp_path, semente):
    """Quebra se os fatores de função pararem de agir e a liderança virar sorte.

    Na semente padrão, os ajudantes lideram mesmo sem os fatores. Nestas cinco,
    sem os fatores, outra função passa à frente em quatro.
    """
    gerar_ok(tmp_path, "--semente", semente)
    contagem = pendencias_por(
        ler_aba(tmp_path / CONTROLE, "Controle"), ler_regras(tmp_path), ler_validades(tmp_path), "função"
    )

    assert lider_e_folga(contagem)[0] == AJUDANTE


def test_algum_treinamento_concentra_as_pendencias(controle, regras, validades):
    """Quebra se "qual treinamento concentra" ficar sem resposta clara."""
    _, folga = lider_e_folga(pendencias_por(controle, regras, validades, "treinamento"))

    assert folga >= 1.5


# ---------- histórico de emissões e renovações ----------

def test_ha_renovacoes_no_historico(emissoes):
    """Quebra se o histórico vier vazio e vw_registro_vigente não tiver o que escolher."""
    tamanhos = Counter(len(datas) for datas in emissoes.values())

    assert tamanhos[2] >= 20
    assert tamanhos[3] >= 5


def test_data_no_controle_e_a_emissao_mais_recente(controle, historico):
    """Quebra se o Controle trouxer uma data mais antiga que a do histórico."""
    por_matricula = {l["Matrícula"]: l for l in controle}
    for linha in historico:
        atual = interpretar_data(por_matricula[linha["Matrícula"]][linha["Treinamento"]])
        assert atual is not None and atual != INVALIDA
        assert linha["Data de emissão"].date() < atual


def test_treinamento_sem_validade_nao_tem_renovacao(historico, validades):
    """Quebra se surgir renovação de item sem vencimento fixo."""
    assert {validades[l["Treinamento"]] for l in historico} <= {12, 24}


@pytest.mark.parametrize("inicio, meses, esperado", [
    (date(2026, 3, 15), 24, date(2028, 3, 15)),
    (date(2024, 2, 29), 12, date(2025, 2, 28)),
    (date(2025, 12, 31), 2, date(2026, 2, 28)),
])
def test_regua_de_meses_dos_testes_segue_o_calendario(inicio, meses, esperado):
    """Confere a régua usada nos testes: o fim de mês se ajusta, como no DATAM."""
    assert somar_meses(inicio, meses) == esperado


def test_renovacao_acontece_perto_do_vencimento_anterior(emissoes, validades):
    """Quebra se a renovação for sorteada longe do vencimento, sem sentido real."""
    for (matricula, treinamento), datas in emissoes.items():
        for anterior, seguinte in zip(datas, datas[1:]):
            vencimento = somar_meses(anterior, validades[treinamento])
            assert abs((seguinte - vencimento).days) <= 60, (matricula, treinamento)


def test_primeira_emissao_acontece_perto_da_admissao_ou_depois(controle, emissoes):
    """Quebra se houver certificado muito anterior à entrada na obra."""
    for linha in funcionarios_unicos(controle):
        admissao = interpretar_data(linha["Admissão"])
        for treinamento in TREINAMENTOS:
            datas = emissoes.get((linha["Matrícula"], treinamento))
            if datas:
                assert datas[0] >= admissao - timedelta(days=30), (linha["Matrícula"], treinamento)


def test_desligado_nao_recebe_emissao_depois_de_sair(controle, emissoes):
    """Quebra se o histórico continuar depois do desligamento."""
    for linha in funcionarios_unicos(controle):
        saida = interpretar_data(linha["Desligamento"])
        if saida is None:
            continue
        for treinamento in TREINAMENTOS:
            for data in emissoes.get((linha["Matrícula"], treinamento), []):
                assert data <= saida, (linha["Matrícula"], treinamento)


def test_carteira_so_existe_depois_de_pemt(controle, emissoes):
    """Quebra se houver carteirinha sem treinamento PEMT, regra da aba Guia."""
    com_carteira = 0
    for linha in funcionarios_unicos(controle):
        carteira = interpretar_data(linha["CARTEIRA"])
        if carteira is None:
            continue
        com_carteira += 1
        primeiras = [
            emissoes[linha["Matrícula"], codigo][0]
            for codigo in ("PEMT1", "PEMT2")
            if (linha["Matrícula"], codigo) in emissoes
        ]
        assert primeiras and carteira >= min(primeiras), linha["Matrícula"]

    assert com_carteira >= 5


# ---------- o resumo impresso precisa ser verdadeiro ----------

def numero(resumo, rotulo):
    casamento = re.search(rf"^\s*{re.escape(rotulo)}: (\d+)", resumo, re.M)
    assert casamento, f"rótulo ausente no resumo: {rotulo}"
    return int(casamento.group(1))


@pytest.mark.parametrize("rotulo, situacao", [
    ("Obrigatórios sem registro", "faltando"),
    ("Vencidos", "vencido"),
    ("Vencem em até 30 dias", "vence_ate_30"),
    ("Vencem de 31 a 60 dias", "vence_31_a_60"),
    ("Vencem de 61 a 90 dias", "vence_61_a_90"),
    ("Válidos por mais de 90 dias", "valido"),
    ("Sem vencimento fixo", "sem_vencimento"),
    ("Condicionais sem data", "condicional_sem_data"),
    ("Não aplicáveis", "nao_aplicavel"),
    ("Com data inválida", "data_invalida"),
])
def test_resumo_impresso_bate_com_a_leitura_independente(resumo, situacoes, rotulo, situacao):
    """Quebra se o gerador divulgar um número que a planilha não confirma."""
    assert numero(resumo, rotulo) == Counter(s for _, _, s in situacoes)[situacao]


def test_resumo_impresso_conta_linhas_e_pessoas_como_a_planilha(resumo, controle, historico):
    """Quebra se o cabeçalho do resumo divergir dos arquivos."""
    assert numero(resumo, "Linhas na aba Controle") == len(controle)
    assert numero(resumo, "Linhas na aba Historico") == len(historico)
    assert numero(resumo, "Funcionários únicos") == len(funcionarios_unicos(controle))
    assert numero(resumo, "Ativos") == len(ativos(controle))
    assert numero(resumo, "Desligados") == 150 - len(ativos(controle))
    assert numero(resumo, "Linhas com data em texto") == sum(isinstance(l["Admissão"], str) for l in controle)
