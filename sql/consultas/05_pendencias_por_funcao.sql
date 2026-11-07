-- Qual função concentra as pendências. Em ordem de taxa de pendência
-- (pendentes / itens obrigatórios); pct_do_total é a fatia de todas as pendências.
WITH por_funcao AS (
    SELECT
        funcao,
        COUNT(DISTINCT matricula) AS funcionarios_ativos,
        COUNT(DISTINCT CASE WHEN pendente = 1 THEN matricula END) AS funcionarios_irregulares,
        SUM(obrigatorio) AS itens_obrigatorios,
        SUM(obrigatorio) - SUM(pendente) AS itens_validos,
        SUM(pendente) AS pendentes,
        SUM(CASE WHEN pendente = 1 AND status = 'Sem registro' THEN 1 ELSE 0 END) AS sem_registro,
        SUM(CASE WHEN pendente = 1 AND status = 'Vencido' THEN 1 ELSE 0 END) AS vencidos
    FROM vw_status_item
    GROUP BY funcao
)
SELECT
    funcao,
    funcionarios_ativos,
    funcionarios_irregulares,
    itens_obrigatorios,
    itens_validos,
    pendentes,
    sem_registro,
    vencidos,
    ROUND(100.0 * itens_validos / itens_obrigatorios, 1) AS pct_conformidade,
    ROUND(100.0 * pendentes / itens_obrigatorios, 1) AS pct_pendencia,
    ROUND(100.0 * pendentes / (SELECT SUM(pendentes) FROM por_funcao), 1) AS pct_do_total
FROM por_funcao
ORDER BY 100.0 * pendentes / itens_obrigatorios DESC, funcao;
