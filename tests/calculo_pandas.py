"""Cálculo independente do gabarito, em pandas, a partir da planilha bruta.

Não usa a versão limpa, o SQL nem os scripts: lê os .xlsx de entrada, limpa do
próprio jeito e refaz as seis respostas. Se o SQL e este cálculo chegam aos
mesmos números por caminhos diferentes, um erro teria de acontecer igual nos
dois para passar despercebido.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pandas as pd


def para_data(valor) -> pd.Timestamp:
    if isinstance(valor, (datetime, pd.Timestamp)):
        return pd.Timestamp(valor).normalize()
    if valor is None or pd.isna(valor):
        return pd.NaT
    # Data impossível, como 31/02/2025, vira NaT e some como se a célula estivesse vazia.
    return pd.to_datetime(str(valor).strip(), format="%d/%m/%Y", errors="coerce")


def sem_espacos(serie: pd.Series) -> pd.Series:
    return serie.map(lambda texto: " ".join(str(texto).split()))


def montar_itens(entrada: Path):
    controle = pd.read_excel(entrada / "controle_largo.xlsx", sheet_name="Controle", dtype=object)
    historico = pd.read_excel(entrada / "controle_largo.xlsx", sheet_name="Historico", dtype=object)
    regras_largas = pd.read_excel(entrada / "parametros.xlsx", sheet_name="Regra_Funcao_Treinamento")
    treinamentos = pd.read_excel(entrada / "parametros.xlsx", sheet_name="Treinamentos")
    alertas = pd.read_excel(entrada / "parametros.xlsx", sheet_name="Alertas", dtype=object)

    alerta = alertas.set_index("Parâmetro")["Valor"]
    referencia = pd.Timestamp(alerta["Data de referência"]).normalize()
    janelas = tuple(int(alerta[f"Janela de alerta {n} (dias)"]) for n in (1, 2, 3))
    codigos = treinamentos["Código"].tolist()

    controle = controle.drop_duplicates(subset="Matrícula", keep="first")
    controle = controle.assign(**{
        coluna: sem_espacos(controle[coluna]) for coluna in ("Nome", "Função", "Equipe", "Situação")
    })
    ativos = controle[controle["Situação"] == "Ativo"]

    emissoes = pd.concat([
        controle[["Matrícula", *codigos]].melt(
            id_vars="Matrícula", var_name="treinamento", value_name="data"
        ),
        historico.rename(columns={"Treinamento": "treinamento", "Data de emissão": "data"}),
    ])
    emissoes["data"] = emissoes["data"].map(para_data)
    vigente = (
        emissoes.dropna(subset=["data"])
        .groupby(["Matrícula", "treinamento"], as_index=False)["data"].max()
    )

    regras = regras_largas.melt(id_vars="Função", var_name="treinamento", value_name="regra")
    catalogo = treinamentos.rename(columns={
        "Código": "treinamento", "Treinamento": "treinamento_nome", "Validade (meses)": "validade",
    })
    itens = (
        ativos[["Matrícula", "Nome", "Função", "Equipe"]]
        .merge(regras, on="Função")
        .merge(catalogo, on="treinamento")
        .merge(vigente, on=["Matrícula", "treinamento"], how="left")
    )
    itens["vencimento"] = pd.to_datetime(pd.Series(
        [
            data + pd.DateOffset(months=int(validade)) if pd.notna(data) and validade > 0 else pd.NaT
            for data, validade in zip(itens["data"], itens["validade"])
        ],
        index=itens.index,
    ))
    itens["dias"] = (itens["vencimento"] - referencia).dt.days
    itens["aplicavel"] = itens["regra"] != "NÃO"
    itens["obrigatorio"] = itens["regra"] == "SIM"
    itens["vencido"] = itens["aplicavel"] & (itens["dias"] < 0)
    itens["sem_registro"] = itens["obrigatorio"] & itens["data"].isna()
    itens["vencido_obrigatorio"] = itens["obrigatorio"] & itens["vencido"]
    itens["pendente"] = itens["sem_registro"] | itens["vencido_obrigatorio"]
    return itens, ativos, referencia, janelas


def resumo_por(itens: pd.DataFrame, ativos: pd.DataFrame, chave: str) -> pd.DataFrame:
    obrigatorios = itens[itens["obrigatorio"]]
    grupos = obrigatorios.groupby(chave)
    tabela = pd.DataFrame({
        "itens_obrigatorios": grupos.size(),
        "pendentes": grupos["pendente"].sum(),
        "sem_registro": grupos["sem_registro"].sum(),
        "vencidos": grupos["vencido_obrigatorio"].sum(),
    })
    tabela["itens_validos"] = tabela["itens_obrigatorios"] - tabela["pendentes"]
    tabela["pct_conformidade"] = 100 * tabela["itens_validos"] / tabela["itens_obrigatorios"]
    tabela["pct_pendencia"] = 100 * tabela["pendentes"] / tabela["itens_obrigatorios"]
    tabela["pct_do_total"] = 100 * tabela["pendentes"] / tabela["pendentes"].sum()
    return tabela


def calcular(entrada: Path) -> dict[str, pd.DataFrame]:
    itens, ativos, referencia, (j1, j2, j3) = montar_itens(entrada)
    obrigatorios = itens[itens["obrigatorio"]]
    pendentes = itens[itens["pendente"]]

    visao_geral = pd.DataFrame([{
        "data_referencia": referencia.date().isoformat(),
        "funcionarios_ativos": len(ativos),
        "funcionarios_irregulares": pendentes["Matrícula"].nunique(),
        "itens_obrigatorios": len(obrigatorios),
        "itens_validos": int((~obrigatorios["pendente"]).sum()),
        "pct_conformidade": 100 * (~obrigatorios["pendente"]).sum() / len(obrigatorios),
        "pendentes_obrigatorios": len(pendentes),
        "obrigatorios_sem_registro": int(pendentes["sem_registro"].sum()),
        "obrigatorios_vencidos": int(pendentes["vencido_obrigatorio"].sum()),
        "itens_vencidos": int(itens["vencido"].sum()),
    }])

    irregulares = (
        pendentes.groupby(["Matrícula", "Nome", "Função", "Equipe"])
        .agg(
            pendencias=("pendente", "size"),
            sem_registro=("sem_registro", "sum"),
            vencidos=("vencido_obrigatorio", "sum"),
            treinamentos=("treinamento", lambda codigos: ", ".join(sorted(codigos))),
        )
        .reset_index()
        .rename(columns={"Matrícula": "matricula", "Nome": "nome", "Função": "funcao", "Equipe": "equipe"})
        .sort_values(["pendencias", "matricula"], ascending=[False, True])
    )

    def vencem_ate(janela):
        return itens[itens["aplicavel"] & itens["dias"].between(0, janela)]

    vencimentos = pd.DataFrame([
        {
            "janela_dias": janela,
            "itens": len(vencem_ate(janela)),
            "itens_obrigatorios": int(vencem_ate(janela)["obrigatorio"].sum()),
            "funcionarios": vencem_ate(janela)["Matrícula"].nunique(),
        }
        for janela in (j1, j2, j3)
    ])

    agenda = vencem_ate(j3).copy()
    agenda["status"] = agenda["dias"].map(
        lambda dias: f"Vence em até {j1} dias" if dias <= j1
        else f"Vence em {j1 + 1} a {j2} dias" if dias <= j2
        else f"Vence em {j2 + 1} a {j3} dias"
    )
    agenda = pd.DataFrame({
        "data_vencimento": agenda["vencimento"].dt.strftime("%Y-%m-%d"),
        "dias_para_vencer": agenda["dias"],
        "matricula": agenda["Matrícula"],
        "nome": agenda["Nome"],
        "funcao": agenda["Função"],
        "equipe": agenda["Equipe"],
        "treinamento": agenda["treinamento"],
        "regra": agenda["regra"],
        "status": agenda["status"],
    }).sort_values(["data_vencimento", "matricula", "treinamento"])

    por_funcao = resumo_por(itens, ativos, "Função")
    por_funcao["funcionarios_ativos"] = ativos.groupby("Função").size()
    por_funcao["funcionarios_irregulares"] = pendentes.groupby("Função")["Matrícula"].nunique()
    por_funcao["funcionarios_irregulares"] = por_funcao["funcionarios_irregulares"].fillna(0)
    por_funcao = (
        por_funcao.rename_axis("funcao").reset_index()
        .sort_values(["pct_pendencia", "funcao"], ascending=[False, True])
    )[[
        "funcao", "funcionarios_ativos", "funcionarios_irregulares", "itens_obrigatorios",
        "itens_validos", "pendentes", "sem_registro", "vencidos",
        "pct_conformidade", "pct_pendencia", "pct_do_total",
    ]]

    nomes = itens.drop_duplicates("treinamento").set_index("treinamento")["treinamento_nome"]
    por_treinamento = resumo_por(itens, ativos, "treinamento")
    por_treinamento["treinamento_nome"] = nomes
    por_treinamento = (
        por_treinamento.rename_axis("treinamento").reset_index()
        .sort_values(["pct_pendencia", "treinamento"], ascending=[False, True])
    )[[
        "treinamento", "treinamento_nome", "itens_obrigatorios", "itens_validos",
        "pendentes", "sem_registro", "vencidos",
        "pct_conformidade", "pct_pendencia", "pct_do_total",
    ]]

    return {
        "01_visao_geral": visao_geral,
        "02_irregulares_hoje": irregulares,
        "03_vencimentos_30_60_90": vencimentos,
        "04_agenda_reciclagem": agenda,
        "05_pendencias_por_funcao": por_funcao,
        "06_pendencias_por_treinamento": por_treinamento,
    }
