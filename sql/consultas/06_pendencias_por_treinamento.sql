-- Qual treinamento concentra as pendências. Só entram os treinamentos que são
-- obrigatórios (SIM) para alguma função; a ordem é a mesma da consulta por função.
WITH por_treinamento AS (
    SELECT
        treinamento,
        treinamento_nome,
        SUM(obrigatorio) AS itens_obrigatorios,
        SUM(obrigatorio) - SUM(pendente) AS itens_validos,
        SUM(pendente) AS pendentes,
        SUM(CASE WHEN pendente = 1 AND status = 'Sem registro' THEN 1 ELSE 0 END) AS sem_registro,
        SUM(CASE WHEN pendente = 1 AND status = 'Vencido' THEN 1 ELSE 0 END) AS vencidos
    FROM vw_status_item
    GROUP BY treinamento, treinamento_nome
    HAVING SUM(obrigatorio) > 0
)
SELECT
    treinamento,
    treinamento_nome,
    itens_obrigatorios,
    itens_validos,
    pendentes,
    sem_registro,
    vencidos,
    ROUND(100.0 * itens_validos / itens_obrigatorios, 1) AS pct_conformidade,
    ROUND(100.0 * pendentes / itens_obrigatorios, 1) AS pct_pendencia,
    ROUND(100.0 * pendentes / (SELECT SUM(pendentes) FROM por_treinamento), 1) AS pct_do_total
FROM por_treinamento
ORDER BY 100.0 * pendentes / itens_obrigatorios DESC, treinamento;
