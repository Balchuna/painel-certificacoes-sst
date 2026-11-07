-- Tabelas da versão limpa (data/limpa/*.csv) e as regras que os dados precisam cumprir.
-- Um CSV que quebre uma regra faz a carga parar, em vez de virar número errado.

-- O SQLite só confere chave estrangeira com isto ligado, em cada conexão.
PRAGMA foreign_keys = ON;

DROP VIEW IF EXISTS vw_pendencias_obrigatorias;
DROP VIEW IF EXISTS vw_status_item;
DROP VIEW IF EXISTS vw_registro_vigente;
DROP TABLE IF EXISTS qualidade_rejeicoes;
DROP TABLE IF EXISTS fato_certificacao;
DROP TABLE IF EXISTS regra_funcao_treinamento;
DROP TABLE IF EXISTS dim_funcionario;
DROP TABLE IF EXISTS dim_treinamento;
DROP TABLE IF EXISTS dim_funcao;
DROP TABLE IF EXISTS parametro;

-- Datas em texto AAAA-MM-DD. "x IS date(x)" recusa 10/01/2026 e 2026-02-31;
-- com "=" no lugar de "IS", uma data inválida passaria, porque NULL não reprova CHECK.

-- Uma linha só: a data de referência e as janelas de alerta, em dias.
CREATE TABLE parametro (
    data_referencia TEXT    NOT NULL CHECK (data_referencia IS date(data_referencia)),
    janela_1        INTEGER NOT NULL CHECK (janela_1 > 0),
    janela_2        INTEGER NOT NULL CHECK (janela_2 > janela_1),
    janela_3        INTEGER NOT NULL CHECK (janela_3 > janela_2)
);

CREATE TRIGGER parametro_uma_linha
BEFORE INSERT ON parametro
WHEN (SELECT COUNT(*) FROM parametro) > 0
BEGIN
    SELECT RAISE(ABORT, 'a tabela parametro tem uma linha só');
END;

CREATE TABLE dim_funcao (
    funcao TEXT PRIMARY KEY
);

-- Validade 0 quer dizer sem vencimento fixo.
CREATE TABLE dim_treinamento (
    codigo         TEXT    PRIMARY KEY,
    nome           TEXT    NOT NULL,
    validade_meses INTEGER NOT NULL CHECK (validade_meses >= 0)
);

CREATE TABLE dim_funcionario (
    matricula    INTEGER PRIMARY KEY,
    nome         TEXT    NOT NULL CHECK (nome <> ''),
    funcao       TEXT    NOT NULL REFERENCES dim_funcao (funcao),
    equipe       TEXT    NOT NULL CHECK (equipe <> ''),
    admissao     TEXT    NOT NULL CHECK (admissao IS date(admissao)),
    situacao     TEXT    NOT NULL CHECK (situacao IN ('Ativo', 'Desligado')),
    desligamento TEXT             CHECK (desligamento IS date(desligamento))
);

CREATE TABLE regra_funcao_treinamento (
    funcao      TEXT NOT NULL REFERENCES dim_funcao (funcao),
    treinamento TEXT NOT NULL REFERENCES dim_treinamento (codigo),
    regra       TEXT NOT NULL CHECK (regra IN ('SIM', 'NÃO', 'CONDICIONAL')),
    PRIMARY KEY (funcao, treinamento)
);

-- Uma linha por emissão ou renovação, venha da aba Controle ou da Historico.
CREATE TABLE fato_certificacao (
    matricula    INTEGER NOT NULL REFERENCES dim_funcionario (matricula),
    treinamento  TEXT    NOT NULL REFERENCES dim_treinamento (codigo),
    data_emissao TEXT    NOT NULL CHECK (data_emissao IS date(data_emissao)),
    origem       TEXT    NOT NULL CHECK (origem IN ('Controle', 'Historico')),
    PRIMARY KEY (matricula, treinamento, data_emissao)
);

-- O que a limpeza descartou. Sem chave estrangeira: a linha descartada pode
-- trazer uma matrícula que não ficou no cadastro.
CREATE TABLE qualidade_rejeicoes (
    aba            TEXT    NOT NULL,
    linha          INTEGER NOT NULL,
    matricula      INTEGER,
    coluna         TEXT,
    valor_original TEXT,
    motivo         TEXT    NOT NULL,
    acao           TEXT    NOT NULL
);
