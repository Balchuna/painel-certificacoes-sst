"""Monta o banco SQLite com a versão limpa e grava o gabarito do painel.

Passo a passo:
  1. recria o banco (--banco) com sql/01_tabelas.sql;
  2. carrega os CSVs da versão limpa (--limpa); um CSV que quebre uma regra
     das tabelas faz tudo parar, com o nome do arquivo;
  3. cria as views de sql/02_views.sql;
  4. roda cada consulta de sql/consultas e grava o resultado em --gabarito,
     com o mesmo nome e extensão .csv.

O gabarito é o que o Power BI precisa bater na mesma data de referência.

Uso:
  python scripts/gerar_gabarito.py
  python scripts/gerar_gabarito.py --limpa outra/limpa --gabarito outro/gabarito
"""
from __future__ import annotations

import argparse
import csv
import re
import sqlite3
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
SQL = RAIZ / "sql"
LIMPA_PADRAO = RAIZ / "data" / "limpa"
BANCO_PADRAO = RAIZ / "data" / "painel.sqlite"
GABARITO_PADRAO = SQL / "gabarito"

# Ordem das chaves estrangeiras: quem é referenciado entra antes.
ORDEM_DE_CARGA = [
    "parametro",
    "dim_funcao",
    "dim_treinamento",
    "dim_funcionario",
    "regra_funcao_treinamento",
    "fato_certificacao",
    "qualidade_rejeicoes",
]
NOME_DE_COLUNA = re.compile(r"[a-z_][a-z0-9_]*")
SQLITE_MINIMO = (3, 44)  # group_concat com ORDER BY


class ErroDeCarga(Exception):
    """A versão limpa não cabe nas tabelas; a carga para e explica."""


def carregar_csv(banco: sqlite3.Connection, tabela: str, caminho: Path) -> int:
    if not caminho.is_file():
        raise ErroDeCarga(f"não achei {caminho}")
    with open(caminho, encoding="utf-8", newline="") as arquivo:
        leitor = csv.reader(arquivo)
        colunas = next(leitor)
        # Célula vazia no CSV vira NULL, para NOT NULL e CHECK valerem.
        linhas = [[valor if valor != "" else None for valor in linha] for linha in leitor]
    invalidas = [coluna for coluna in colunas if not NOME_DE_COLUNA.fullmatch(coluna)]
    if invalidas:
        raise ErroDeCarga(f"{caminho.name}: cabeçalho inesperado {invalidas}")
    comando = (
        f"INSERT INTO {tabela} ({', '.join(colunas)}) "
        f"VALUES ({', '.join('?' * len(colunas))})"
    )
    try:
        banco.executemany(comando, linhas)
    except sqlite3.Error as erro:
        raise ErroDeCarga(f"{caminho.name} quebra uma regra das tabelas: {erro}") from None
    return len(linhas)


def montar_banco(caminho: Path, limpa: Path) -> sqlite3.Connection:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.unlink(missing_ok=True)
    banco = sqlite3.connect(caminho)
    banco.execute("PRAGMA foreign_keys = ON")
    try:
        banco.executescript((SQL / "01_tabelas.sql").read_text(encoding="utf-8"))
        with banco:
            for tabela in ORDEM_DE_CARGA:
                carregar_csv(banco, tabela, limpa / f"{tabela}.csv")
        banco.executescript((SQL / "02_views.sql").read_text(encoding="utf-8"))
    except ErroDeCarga:
        # Não deixa um banco pela metade com cara de pronto.
        banco.close()
        caminho.unlink(missing_ok=True)
        raise
    return banco


def gravar_resultado(cursor: sqlite3.Cursor, caminho: Path) -> int:
    colunas = [descricao[0] for descricao in cursor.description]
    linhas = cursor.fetchall()
    with open(caminho, "w", encoding="utf-8", newline="") as arquivo:
        escritor = csv.writer(arquivo, lineterminator="\n")
        escritor.writerow(colunas)
        escritor.writerows(["" if valor is None else valor for valor in linha] for linha in linhas)
    return len(linhas)


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Gera o gabarito SQL do painel.")
    parser.add_argument("--limpa", type=Path, default=LIMPA_PADRAO)
    parser.add_argument("--banco", type=Path, default=BANCO_PADRAO)
    parser.add_argument("--gabarito", type=Path, default=GABARITO_PADRAO)
    args = parser.parse_args()

    if sqlite3.sqlite_version_info < SQLITE_MINIMO:
        sys.exit(
            f"erro: as consultas pedem SQLite {'.'.join(map(str, SQLITE_MINIMO))} ou mais novo; "
            f"este Python traz o {sqlite3.sqlite_version}"
        )
    try:
        banco = montar_banco(args.banco, args.limpa)
    except ErroDeCarga as erro:
        sys.exit(f"erro: {erro}")

    try:
        args.gabarito.mkdir(parents=True, exist_ok=True)
        print(f"Banco montado em {args.banco}. Gabarito gravado em {args.gabarito}:")
        for consulta in sorted((SQL / "consultas").glob("*.sql")):
            cursor = banco.execute(consulta.read_text(encoding="utf-8"))
            quantidade = gravar_resultado(cursor, args.gabarito / f"{consulta.stem}.csv")
            print(f"  {consulta.stem}.csv: {quantidade} linhas")

        banco.row_factory = sqlite3.Row
        visao = dict(banco.execute(
            (SQL / "consultas" / "01_visao_geral.sql").read_text(encoding="utf-8")
        ).fetchone())
    finally:
        banco.close()

    print()
    print(f"Na data de referência {visao['data_referencia']}:")
    print(f"  funcionários ativos: {visao['funcionarios_ativos']}")
    print(f"  funcionários irregulares: {visao['funcionarios_irregulares']}")
    print(
        f"  itens obrigatórios: {visao['itens_obrigatorios']}, válidos: {visao['itens_validos']} "
        f"({visao['pct_conformidade']}% de conformidade)"
    )
    print(
        f"  pendentes obrigatórios: {visao['pendentes_obrigatorios']} "
        f"({visao['obrigatorios_sem_registro']} sem registro, "
        f"{visao['obrigatorios_vencidos']} vencidos)"
    )


if __name__ == "__main__":
    main()
