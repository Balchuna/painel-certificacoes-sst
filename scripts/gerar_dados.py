"""Gera os dados sintéticos de entrada do Painel de Certificações SST.

Todos os funcionários são fictícios. O script não lê nenhum arquivo: nomes,
datas e pendências saem de um sorteio com semente fixa. A mesma semente e a
mesma data de referência geram sempre os mesmos arquivos.

Saída, na pasta indicada em --saida:
  controle_largo.xlsx  imita uma planilha real e bagunçada, com uma coluna por
                       treinamento. A aba Controle traz a emissão mais recente
                       de cada item; a aba Historico, as emissões anteriores.
  parametros.xlsx      regras por função, validades e janelas de alerta.

Uso:
  python scripts/gerar_dados.py
  python scripts/gerar_dados.py --semente 7 --data-referencia 2026-06-01
"""
from __future__ import annotations

import argparse
import calendar
import io
import random
import re
import sys
from collections import Counter
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from itertools import product
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

from openpyxl import Workbook
from openpyxl.styles import Font
from openpyxl.utils import get_column_letter

SEMENTE_PADRAO = 20261101
DATA_REFERENCIA_PADRAO = date(2026, 11, 1)
PASTA_SAIDA_PADRAO = Path(__file__).resolve().parents[1] / "data" / "entrada"

# ---------- Regras: viram parametros.xlsx ----------

# Código, nome e validade em meses. Validade 0 = sem vencimento fixo.
# Os códigos e as validades seguem a aba Config_SST da referência.
TREINAMENTOS = {
    "ASO": ("ASO: aptidão ocupacional", 12),
    "NR01": ("NR-01: integração e PGR", 0),
    "NR05": ("NR-05: CIPA", 0),
    "NR06": ("NR-06: EPI", 0),
    "NR12": ("NR-12: máquinas e equipamentos", 0),
    "NR18": ("NR-18: básico na construção", 24),
    "NR34": ("NR-34: trabalho a quente", 0),
    "NR35": ("NR-35: trabalho em altura", 24),
    "PEMT1": ("PEMT modelo 1: lança articulada", 24),
    "PEMT2": ("PEMT modelo 2: tesoura", 24),
    "ANDAIME": ("Montagem de andaimes", 0),
    "CARTEIRA": ("Carteirinha PEMT", 0),
}
CODIGOS = list(TREINAMENTOS)

S, C, N = "SIM", "CONDICIONAL", "NÃO"

# A matriz segue a Config_SST, com uma diferença: a referência não tem nenhum
# NÃO. Nove células CONDICIONAL viraram NÃO para o caso "não aplicável" existir.
# Isto é parâmetro do modelo, não interpretação jurídica das NRs.
#                                     ASO NR01 NR05 NR06 NR12 NR18 NR34 NR35 PEMT1 PEMT2 AND CART
REGRAS = {
    "MONTADOR DE STEEL FRAME":        [S, S, C, S, C, S, C, S, C, C, C, C],
    "AJ. DE MONTADOR DE STEEL FRAME": [S, S, C, S, C, S, N, S, C, C, C, C],
    "ENCARREGADO DE OBRAS":           [S, S, C, S, C, S, C, C, C, C, C, C],
    "MONTADOR DE GESSO":              [S, S, C, S, C, S, N, C, N, C, C, C],
    "TEC. DE SEGURANÇA DO TRABALHO":  [S, S, C, S, N, S, N, C, N, N, N, N],
}
JANELAS_ALERTA = (30, 60, 90)

# ---------- Composição da obra fictícia ----------

N_FUNCIONARIOS = 150
N_DESLIGADOS = 12
N_LINHAS_DATA_TEXTO = 30
QUANTIDADE_POR_FUNCAO = {
    "MONTADOR DE STEEL FRAME": 60,
    "AJ. DE MONTADOR DE STEEL FRAME": 45,
    "MONTADOR DE GESSO": 30,
    "ENCARREGADO DE OBRAS": 9,
    "TEC. DE SEGURANÇA DO TRABALHO": 6,
}
EQUIPES = ("Equipe Alfa", "Equipe Beta", "Equipe Gama")
PRIMEIRA_MATRICULA = 7001
INICIO_ADMISSOES = date(2023, 1, 2)
FIM_ADMISSOES = date(2026, 12, 31)

# Sem os nomes usados nos exemplos do modelo de referência.
PRENOMES = (
    "Adriano", "Alessandra", "Amanda", "Antônia", "Bruna", "Caio", "Camila", "Cláudio",
    "Daniela", "Débora", "Edson", "Elaine", "Fábio", "Gabriela", "Gilberto", "Helena",
    "Heitor", "Inês", "Ivan", "Jéssica", "Júlio", "Karina", "Leandro", "Lúcia",
    "Márcio", "Mirela", "Natália", "Nelson", "Otávio", "Patrícia", "Paulo", "Quitéria",
    "Raquel", "Renato", "Sandra", "Sérgio", "Tânia", "Ubirajara", "Valéria", "Vinícius",
)
SOBRENOMES = (
    "Abreu", "Aguiar", "Amaral", "Araújo", "Assunção", "Bastos", "Brandão", "Caldeira",
    "Campos", "Conceição", "Correia", "Dantas", "Duarte", "Esteves", "Falcão", "Farias",
    "Fontes", "Galvão", "Guimarães", "Henriques", "Jardim", "Leal", "Macedo", "Magalhães",
    "Matos", "Meireles", "Moura", "Nogueira", "Paiva", "Pacheco", "Queiroz", "Rezende",
    "Sales", "Santana", "Simões", "Tavares", "Teixeira", "Valente", "Vidal", "Xavier",
)

# ---------- Chances do sorteio ----------

# Item obrigatório que o funcionário nunca fez.
CHANCE_NUNCA_FEZ = {"ASO": 0.02, "NR01": 0.04, "NR06": 0.05, "NR18": 0.06, "NR35": 0.09}
# Item condicional que se aplica ao funcionário (designação ou atividade).
CHANCE_CONDICIONAL = {
    "NR05": 0.08, "NR12": 0.15, "NR34": 0.06, "NR35": 0.55,
    "PEMT1": 0.25, "PEMT2": 0.30, "ANDAIME": 0.20,
}
CHANCE_CARTEIRA_COM_PEMT = 0.70
# A cada vencimento, chance de o funcionário não renovar mais.
CHANCE_NAO_RENOVA = {"ASO": 0.05, "NR18": 0.05, "NR35": 0.09, "PEMT1": 0.10, "PEMT2": 0.10}
# Chance de renovar depois de vencer, e não um pouco antes.
CHANCE_RENOVA_ATRASADO = 0.15
# Multiplicam as chances acima. É isto que cria a concentração de pendências:
# um achado do painel sobre função ou equipe reflete estes números, não a realidade.
FATOR_FUNCAO = {
    "MONTADOR DE STEEL FRAME": 1.0,
    "AJ. DE MONTADOR DE STEEL FRAME": 1.8,
    "MONTADOR DE GESSO": 1.2,
    "ENCARREGADO DE OBRAS": 0.5,
    "TEC. DE SEGURANÇA DO TRABALHO": 0.4,
}
FATOR_EQUIPE = {"Equipe Alfa": 0.8, "Equipe Beta": 1.0, "Equipe Gama": 1.5}
# Dias entre a admissão e a primeira emissão de cada item.
PRAZO_PRIMEIRA_EMISSAO = {
    "ASO": (-7, 0), "NR01": (0, 3), "NR06": (0, 5), "NR18": (0, 20), "NR35": (0, 30),
}
PRAZO_ITEM_CONDICIONAL = (5, 180)

# ---------- Bagunça da planilha ----------

CHANCE_ESPACO_NOME = 0.18
CHANCE_ESPACO_FUNCAO = 0.12
CHANCE_ESPACO_EQUIPE = 0.10
CHANCE_ESPACO_DATA_TEXTO = 0.10

FONTE = Font(name="Arial", size=10)
FONTE_CABECALHO = Font(name="Arial", size=10, bold=True)
FORMATO_DATA = "dd/mm/yyyy"
LARGURA_MINIMA = 12
AVISO_SINTETICO = (
    "Dados sintéticos: funcionários, nomes, matrículas e datas são fictícios, "
    "gerados por scripts/gerar_dados.py."
)


@dataclass
class Funcionario:
    matricula: int
    nome: str
    funcao: str
    equipe: str
    admissao: date
    desligamento: date | None = None
    # Código do treinamento -> datas de emissão em ordem crescente.
    emissoes: dict[str, list[date]] = field(default_factory=dict)

    @property
    def situacao(self) -> str:
        return "Desligado" if self.desligamento else "Ativo"

    def regra(self, codigo: str) -> str:
        return REGRAS[self.funcao][CODIGOS.index(codigo)]


@dataclass
class Bagunca:
    """Quais defeitos foram plantados, e onde."""
    matriculas_data_texto: set[int]
    matricula_duplicada: int
    posicao_duplicada: int
    matricula_invalida: int
    codigo_invalido: str
    valor_invalido: str


def somar_meses(inicio: date, meses: int) -> date:
    """Soma meses de calendário, como a função DATAM do Excel."""
    total = inicio.year * 12 + inicio.month - 1 + meses
    ano, mes = total // 12, total % 12 + 1
    return date(ano, mes, min(inicio.day, calendar.monthrange(ano, mes)[1]))


def sortear_funcionarios(rng: random.Random, data_ref: date) -> list[Funcionario]:
    fim = min(FIM_ADMISSOES, data_ref - timedelta(days=7))
    janela = (fim - INICIO_ADMISSOES).days
    admissoes = sorted(
        INICIO_ADMISSOES + timedelta(days=rng.randint(0, janela))
        for _ in range(N_FUNCIONARIOS)
    )

    combinacoes = [c for c in product(PRENOMES, SOBRENOMES, SOBRENOMES) if c[1] != c[2]]
    nomes = [" ".join(c) for c in rng.sample(combinacoes, N_FUNCIONARIOS)]

    funcoes = [f for f, qtd in QUANTIDADE_POR_FUNCAO.items() for _ in range(qtd)]
    rng.shuffle(funcoes)

    funcionarios = [
        Funcionario(
            matricula=PRIMEIRA_MATRICULA + i,
            nome=nomes[i],
            funcao=funcoes[i],
            equipe=rng.choice(EQUIPES),
            admissao=admissoes[i],
        )
        for i in range(N_FUNCIONARIOS)
    ]

    # Só desliga quem teve tempo de trabalhar e sair antes da data de referência.
    elegiveis = [f for f in funcionarios if (data_ref - f.admissao).days >= 120]
    for funcionario in rng.sample(elegiveis, N_DESLIGADOS):
        folga = (data_ref - funcionario.admissao).days - 61
        funcionario.desligamento = funcionario.admissao + timedelta(days=60 + rng.randint(0, folga))
    return funcionarios


def chance_ajustada(base: float, funcionario: Funcionario) -> float:
    return min(0.95, base * FATOR_FUNCAO[funcionario.funcao] * FATOR_EQUIPE[funcionario.equipe])


def sortear_renovacoes(
    rng: random.Random, primeira: date, validade: int, limite: date, chance_parar: float
) -> list[date]:
    """Caminha de vencimento em vencimento até o limite ou até parar de renovar."""
    datas = [primeira]
    if validade == 0:
        return datas
    while True:
        vencimento = somar_meses(datas[-1], validade)
        if rng.random() < CHANCE_RENOVA_ATRASADO:
            seguinte = vencimento + timedelta(days=rng.randint(1, 45))
        else:
            seguinte = vencimento - timedelta(days=rng.randint(0, 30))
        if seguinte > limite or rng.random() < chance_parar:
            return datas
        datas.append(seguinte)


def sortear_emissoes(rng: random.Random, funcionario: Funcionario, data_ref: date) -> None:
    limite = funcionario.desligamento or data_ref
    for codigo in CODIGOS:
        regra = funcionario.regra(codigo)
        if regra == N or codigo == "CARTEIRA":
            continue
        if regra == S:
            aplica = rng.random() >= chance_ajustada(CHANCE_NUNCA_FEZ[codigo], funcionario)
            prazo = PRAZO_PRIMEIRA_EMISSAO[codigo]
        else:
            aplica = rng.random() < CHANCE_CONDICIONAL[codigo]
            prazo = PRAZO_ITEM_CONDICIONAL
        if not aplica:
            continue
        primeira = funcionario.admissao + timedelta(days=rng.randint(*prazo))
        if primeira > limite:
            continue  # Admitido há pouco: ainda não deu tempo de fazer.
        validade = TREINAMENTOS[codigo][1]
        chance_parar = chance_ajustada(CHANCE_NAO_RENOVA.get(codigo, 0.0), funcionario)
        funcionario.emissoes[codigo] = sortear_renovacoes(rng, primeira, validade, limite, chance_parar)

    pemts = [funcionario.emissoes[c][0] for c in ("PEMT1", "PEMT2") if c in funcionario.emissoes]
    if pemts and funcionario.regra("CARTEIRA") == C and rng.random() < CHANCE_CARTEIRA_COM_PEMT:
        emissao = min(pemts) + timedelta(days=rng.randint(3, 30))
        if emissao <= limite:
            funcionario.emissoes["CARTEIRA"] = [emissao]


def plantar_bagunca(rng: random.Random, funcionarios: list[Funcionario]) -> Bagunca:
    """Sorteia onde cada defeito cai, sem que um defeito esbarre no outro."""
    matriculas = [f.matricula for f in funcionarios]
    com_texto = set(rng.sample(matriculas, N_LINHAS_DATA_TEXTO))

    com_data_real = [f for f in funcionarios if f.matricula not in com_texto and not f.desligamento]

    # A data inválida cai em item obrigatório, sem emissão anterior: rejeitada a
    # célula, a resposta certa é uma só, o item fica sem registro.
    candidatas = [
        (f, c) for f in com_data_real for c in CODIGOS
        if f.regra(c) == S and len(f.emissoes.get(c, [])) == 1
    ]
    invalido, codigo = rng.choice(candidatas)

    duplicado = rng.choice([f for f in com_data_real if f is not invalido])
    original = funcionarios.index(duplicado)
    distantes = [i for i in range(N_FUNCIONARIOS + 1) if abs(i - original) >= 10]

    return Bagunca(
        matriculas_data_texto=com_texto,
        matricula_duplicada=duplicado.matricula,
        posicao_duplicada=rng.choice(distantes),
        matricula_invalida=invalido.matricula,
        codigo_invalido=codigo,
        # O dia 31 de fevereiro nunca existe, em nenhum ano.
        valor_invalido=f"31/02/{invalido.emissoes[codigo][-1].year}",
    )


def com_espacos(rng: random.Random, texto: str, chance: float) -> str:
    if rng.random() >= chance:
        return texto
    return rng.choice((f" {texto}", f"{texto} ", f"{texto}  "))


def nome_com_espacos(rng: random.Random, nome: str) -> str:
    if rng.random() >= CHANCE_ESPACO_NOME:
        return nome
    return rng.choice((f" {nome}", f"{nome} ", nome.replace(" ", "  ", 1)))


def data_em_texto(rng: random.Random, valor: date | None) -> str | None:
    if valor is None:
        return None
    return com_espacos(rng, valor.strftime("%d/%m/%Y"), CHANCE_ESPACO_DATA_TEXTO)


def montar_linha(
    rng: random.Random, funcionario: Funcionario, bagunca: Bagunca, como_texto: bool, nome: str | None = None
) -> list:
    def data(valor: date | None):
        return data_em_texto(rng, valor) if como_texto else valor

    linha = [
        funcionario.matricula,
        nome if nome is not None else nome_com_espacos(rng, funcionario.nome),
        com_espacos(rng, funcionario.funcao, CHANCE_ESPACO_FUNCAO),
        com_espacos(rng, funcionario.equipe, CHANCE_ESPACO_EQUIPE),
        data(funcionario.admissao),
        funcionario.situacao,
        data(funcionario.desligamento),
    ]
    for codigo in CODIGOS:
        datas = funcionario.emissoes.get(codigo)
        if funcionario.matricula == bagunca.matricula_invalida and codigo == bagunca.codigo_invalido:
            linha.append(bagunca.valor_invalido)
        else:
            linha.append(data(datas[-1]) if datas else None)
    return linha


def escrever_aba(aba, cabecalho: list[str], linhas: list[list]) -> None:
    aba.append(cabecalho)
    for linha in linhas:
        aba.append(linha)
    for fileira in aba.iter_rows():
        for celula in fileira:
            celula.font = FONTE_CABECALHO if celula.row == 1 else FONTE
            if isinstance(celula.value, (date, datetime)):
                celula.number_format = FORMATO_DATA
    # Sem largura gravada, o Excel mostra ######## nas colunas de data.
    for indice, coluna in enumerate(aba.iter_cols(), start=1):
        maior = max(
            len(FORMATO_DATA) if isinstance(c.value, (date, datetime)) else len(str(c.value or ""))
            for c in coluna
        )
        aba.column_dimensions[get_column_letter(indice)].width = max(maior + 2, LARGURA_MINIMA)
    aba.freeze_panes = "A2"


def escrever_leia_me(planilha: Workbook, linhas: list[str]) -> None:
    aba = planilha.create_sheet("Leia-me")
    for linha in [AVISO_SINTETICO, *linhas]:
        aba.append([linha])
    for fileira in aba.iter_rows():
        fileira[0].font = FONTE
    aba.column_dimensions["A"].width = 110


def salvar_sem_relogio(planilha: Workbook, caminho: Path, data_ref: date) -> None:
    """Salva o xlsx sem nenhuma marca do horário em que o script rodou.

    O openpyxl grava a hora atual nos metadados e o zip grava a hora em cada
    arquivo interno. Aqui as duas viram a data de referência, para que duas
    execuções produzam exatamente os mesmos bytes.
    """
    instante = datetime(data_ref.year, data_ref.month, data_ref.day)
    planilha.properties.creator = "scripts/gerar_dados.py"
    planilha.properties.created = instante

    memoria = io.BytesIO()
    planilha.save(memoria)

    carimbo = instante.strftime("%Y-%m-%dT%H:%M:%SZ").encode()
    with ZipFile(memoria) as origem, ZipFile(caminho, "w", ZIP_DEFLATED) as destino:
        for item in origem.infolist():
            conteudo = origem.read(item.filename)
            if item.filename == "docProps/core.xml":
                conteudo = re.sub(
                    rb"(<dcterms:modified[^>]*>)[^<]*(</dcterms:modified>)",
                    rb"\g<1>" + carimbo + rb"\g<2>",
                    conteudo,
                )
            novo = ZipInfo(item.filename, date_time=instante.timetuple()[:6])
            novo.compress_type = ZIP_DEFLATED
            destino.writestr(novo, conteudo)


def escrever_controle(
    rng: random.Random, funcionarios: list[Funcionario], bagunca: Bagunca, caminho: Path, data_ref: date
) -> tuple[int, int, int]:
    """Devolve (linhas no Controle, linhas com data em texto, linhas no Historico)."""
    linhas = [
        montar_linha(rng, f, bagunca, como_texto=f.matricula in bagunca.matriculas_data_texto)
        for f in funcionarios
    ]
    # A cópia do duplicado vem com as datas em texto e o nome sujo, como acontece
    # quando alguém redigita a mesma pessoa em outro ponto da planilha.
    duplicado = next(f for f in funcionarios if f.matricula == bagunca.matricula_duplicada)
    copia = montar_linha(rng, duplicado, bagunca, como_texto=True, nome=f" {duplicado.nome}  ")
    linhas.insert(bagunca.posicao_duplicada, copia)

    anteriores = [
        [f.matricula, codigo, emissao]
        for f in funcionarios
        for codigo, datas in f.emissoes.items()
        for emissao in datas[:-1]
    ]

    planilha = Workbook()
    aba = planilha.active
    aba.title = "Controle"
    cabecalho = ["Matrícula", "Nome", "Função", "Equipe", "Admissão", "Situação", "Desligamento", *CODIGOS]
    escrever_aba(aba, cabecalho, linhas)
    escrever_aba(planilha.create_sheet("Historico"), ["Matrícula", "Treinamento", "Data de emissão"], anteriores)
    escrever_leia_me(planilha, [
        "Aba Controle: uma linha por funcionário, uma coluna por treinamento, com a emissão mais recente.",
        "Aba Historico: as emissões anteriores, uma por linha.",
        "A aba Controle tem defeitos de propósito, para a etapa de limpeza: datas como texto, "
        "espaços sobrando, um funcionário duplicado e uma data inválida.",
    ])
    salvar_sem_relogio(planilha, caminho, data_ref)
    indice_admissao = cabecalho.index("Admissão")
    linhas_texto = sum(isinstance(linha[indice_admissao], str) for linha in linhas)
    return len(linhas), linhas_texto, len(anteriores)


def escrever_parametros(caminho: Path, data_ref: date) -> None:
    planilha = Workbook()
    aba = planilha.active
    aba.title = "Regra_Funcao_Treinamento"
    escrever_aba(aba, ["Função", *CODIGOS], [[f, *regras] for f, regras in REGRAS.items()])
    escrever_aba(
        planilha.create_sheet("Treinamentos"),
        ["Código", "Treinamento", "Validade (meses)"],
        [[codigo, nome, meses] for codigo, (nome, meses) in TREINAMENTOS.items()],
    )
    escrever_aba(
        planilha.create_sheet("Alertas"),
        ["Parâmetro", "Valor"],
        [
            ["Data de referência", data_ref],
            *[[f"Janela de alerta {i} (dias)", dias] for i, dias in enumerate(JANELAS_ALERTA, start=1)],
        ],
    )
    escrever_leia_me(planilha, [
        "SIM = obrigatório; CONDICIONAL = depende de designação ou atividade; NÃO = não se aplica.",
        "Validade 0 = sem vencimento fixo.",
        "As regras são parâmetros do modelo, não interpretação jurídica das NRs.",
    ])
    salvar_sem_relogio(planilha, caminho, data_ref)


def situacao_do_item(funcionario: Funcionario, codigo: str, bagunca: Bagunca, data_ref: date) -> str:
    if funcionario.matricula == bagunca.matricula_invalida and codigo == bagunca.codigo_invalido:
        return "Com data inválida"
    datas = funcionario.emissoes.get(codigo)
    if not datas:
        return {
            S: "Obrigatórios sem registro",
            C: "Condicionais sem data",
            N: "Não aplicáveis",
        }[funcionario.regra(codigo)]
    validade = TREINAMENTOS[codigo][1]
    if validade == 0:
        return "Sem vencimento fixo"
    dias = (somar_meses(datas[-1], validade) - data_ref).days
    if dias < 0:
        return "Vencidos"
    if dias <= 30:
        return "Vencem em até 30 dias"
    if dias <= 60:
        return "Vencem de 31 a 60 dias"
    if dias <= 90:
        return "Vencem de 61 a 90 dias"
    return "Válidos por mais de 90 dias"


def montar_resumo(
    funcionarios: list[Funcionario], bagunca: Bagunca, semente: int, data_ref: date,
    linhas_controle: int, linhas_texto: int, linhas_historico: int,
) -> list[str]:
    ativos = [f for f in funcionarios if not f.desligamento]
    contagem = Counter(situacao_do_item(f, c, bagunca, data_ref) for f in ativos for c in CODIGOS)
    ordem = (
        "Obrigatórios sem registro", "Vencidos", "Vencem em até 30 dias", "Vencem de 31 a 60 dias",
        "Vencem de 61 a 90 dias", "Válidos por mais de 90 dias", "Sem vencimento fixo",
        "Condicionais sem data", "Não aplicáveis", "Com data inválida",
    )
    return [
        f"Semente: {semente}",
        f"Data de referência: {data_ref.isoformat()}",
        "",
        f"Linhas na aba Controle: {linhas_controle}",
        f"Linhas na aba Historico: {linhas_historico}",
        f"Funcionários únicos: {len(funcionarios)}",
        f"Ativos: {len(ativos)}",
        f"Desligados: {len(funcionarios) - len(ativos)}",
        "",
        "Defeitos plantados na aba Controle:",
        f"  Linhas com data em texto: {linhas_texto}",
        f"  Matrícula duplicada: {bagunca.matricula_duplicada}",
        f"  Data inválida: matrícula {bagunca.matricula_invalida}, coluna "
        f"{bagunca.codigo_invalido}, valor {bagunca.valor_invalido}",
        "",
        f"Itens de funcionários ativos em {data_ref.isoformat()} "
        f"({len(ativos)} ativos x {len(CODIGOS)} treinamentos = {len(ativos) * len(CODIGOS)}):",
        *[f"  {rotulo}: {contagem[rotulo]}" for rotulo in ordem],
    ]


def ler_data_referencia(texto: str) -> date:
    try:
        return date.fromisoformat(texto)
    except ValueError:
        raise argparse.ArgumentTypeError(f"use o formato AAAA-MM-DD, recebi {texto!r}") from None


def main() -> None:
    parser = argparse.ArgumentParser(description="Gera os dados sintéticos de entrada do painel.")
    parser.add_argument("--semente", type=int, default=SEMENTE_PADRAO)
    parser.add_argument("--data-referencia", type=ler_data_referencia, default=DATA_REFERENCIA_PADRAO)
    parser.add_argument("--saida", type=Path, default=PASTA_SAIDA_PADRAO)
    args = parser.parse_args()

    data_ref = args.data_referencia
    if (min(FIM_ADMISSOES, data_ref - timedelta(days=7)) - INICIO_ADMISSOES).days < 365:
        parser.error("--data-referencia precisa ser pelo menos um ano depois de 02/01/2023")

    rng = random.Random(args.semente)
    funcionarios = sortear_funcionarios(rng, data_ref)
    for funcionario in funcionarios:
        sortear_emissoes(rng, funcionario, data_ref)
    bagunca = plantar_bagunca(rng, funcionarios)

    args.saida.mkdir(parents=True, exist_ok=True)
    linhas_controle, linhas_texto, linhas_historico = escrever_controle(
        rng, funcionarios, bagunca, args.saida / "controle_largo.xlsx", data_ref
    )
    escrever_parametros(args.saida / "parametros.xlsx", data_ref)

    sys.stdout.reconfigure(encoding="utf-8")
    print("\n".join(montar_resumo(
        funcionarios, bagunca, args.semente, data_ref, linhas_controle, linhas_texto, linhas_historico
    )))


if __name__ == "__main__":
    main()
