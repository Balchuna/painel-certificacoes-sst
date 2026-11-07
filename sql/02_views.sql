-- Views do SQL de referência. Dependem das tabelas de 01_tabelas.sql.

-- A emissão mais recente de cada funcionário em cada treinamento, com o vencimento.
CREATE VIEW vw_registro_vigente AS
WITH emissoes AS (
    SELECT
        matricula,
        treinamento,
        data_emissao,
        ROW_NUMBER() OVER (
            PARTITION BY matricula, treinamento ORDER BY data_emissao DESC
        ) AS ordem,
        COUNT(*) OVER (PARTITION BY matricula, treinamento) AS emissoes
    FROM fato_certificacao
),
vigente AS (
    SELECT
        e.matricula,
        e.treinamento,
        e.data_emissao,
        e.emissoes,
        t.validade_meses,
        -- O SQLite passa do fim do mês: 2024-01-31 + 1 mês dá 2024-03-02.
        date(e.data_emissao, '+' || t.validade_meses || ' months') AS soma_bruta
    FROM emissoes AS e
    JOIN dim_treinamento AS t ON t.codigo = e.treinamento
    WHERE e.ordem = 1
)
SELECT
    matricula,
    treinamento,
    data_emissao,
    emissoes,
    validade_meses,
    CASE
        WHEN validade_meses = 0 THEN NULL
        -- Mesmo dia do mês da emissão: a soma não passou do fim do mês.
        WHEN strftime('%d', soma_bruta) = strftime('%d', data_emissao) THEN soma_bruta
        -- Passou: volta para o último dia do mês certo, como DATAM (Excel) e EDATE (Power BI).
        ELSE date(soma_bruta, 'start of month', '-1 day')
    END AS data_vencimento
FROM vigente;


-- Um item por funcionário ativo e treinamento, com a situação na data de referência.
CREATE VIEW vw_status_item AS
WITH itens AS (
    SELECT
        f.matricula,
        f.nome,
        f.funcao,
        f.equipe,
        t.codigo AS treinamento,
        t.nome AS treinamento_nome,
        r.regra,
        v.data_emissao,
        v.data_vencimento,
        CAST(julianday(v.data_vencimento) - julianday(p.data_referencia) AS INTEGER)
            AS dias_para_vencer,
        p.janela_1,
        p.janela_2,
        p.janela_3
    FROM dim_funcionario AS f
    CROSS JOIN parametro AS p
    JOIN regra_funcao_treinamento AS r ON r.funcao = f.funcao
    JOIN dim_treinamento AS t ON t.codigo = r.treinamento
    LEFT JOIN vw_registro_vigente AS v
        ON v.matricula = f.matricula AND v.treinamento = t.codigo
    WHERE f.situacao = 'Ativo'
),
classificados AS (
    SELECT
        *,
        CASE
            -- NÃO se aplica à função: a data, se houver, não muda nada.
            WHEN regra = 'NÃO' THEN 'Não aplicável'
            WHEN data_emissao IS NULL AND regra = 'SIM' THEN 'Sem registro'
            WHEN data_emissao IS NULL THEN 'Condicional sem registro'
            WHEN data_vencimento IS NULL THEN 'Sem vencimento'
            -- Vencer na própria data de referência ainda vale: vence hoje, não venceu.
            WHEN dias_para_vencer < 0 THEN 'Vencido'
            WHEN dias_para_vencer <= janela_1 THEN 'Vence em até ' || janela_1 || ' dias'
            WHEN dias_para_vencer <= janela_2
                THEN 'Vence em ' || (janela_1 + 1) || ' a ' || janela_2 || ' dias'
            WHEN dias_para_vencer <= janela_3
                THEN 'Vence em ' || (janela_2 + 1) || ' a ' || janela_3 || ' dias'
            ELSE 'Válido'
        END AS status
    FROM itens
)
SELECT
    matricula,
    nome,
    funcao,
    equipe,
    treinamento,
    treinamento_nome,
    regra,
    CASE WHEN regra = 'SIM' THEN 1 ELSE 0 END AS obrigatorio,
    data_emissao,
    data_vencimento,
    dias_para_vencer,
    status,
    -- Pendente só conta item obrigatório. CONDICIONAL vencido aparece no status, não aqui.
    CASE WHEN regra = 'SIM' AND status IN ('Sem registro', 'Vencido') THEN 1 ELSE 0 END
        AS pendente
FROM classificados;


-- O que deixa um funcionário irregular hoje: item obrigatório sem registro ou vencido.
CREATE VIEW vw_pendencias_obrigatorias AS
SELECT
    matricula,
    nome,
    funcao,
    equipe,
    treinamento,
    treinamento_nome,
    status AS motivo,
    data_emissao,
    data_vencimento,
    dias_para_vencer
FROM vw_status_item
WHERE pendente = 1;
