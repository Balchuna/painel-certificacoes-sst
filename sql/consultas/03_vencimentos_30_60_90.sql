-- O que vence nos próximos 30, 60 e 90 dias (as janelas da tabela parametro).
-- As janelas são cumulativas: "até 60 dias" inclui os de até 30. Conta do dia 0
-- (vence na data de referência) até o fim da janela, para SIM e CONDICIONAL com data.
WITH janelas AS (
    SELECT janela_1 AS janela_dias FROM parametro
    UNION ALL
    SELECT janela_2 FROM parametro
    UNION ALL
    SELECT janela_3 FROM parametro
)
SELECT
    j.janela_dias,
    COUNT(i.matricula) AS itens,
    COALESCE(SUM(i.obrigatorio), 0) AS itens_obrigatorios,
    COUNT(DISTINCT i.matricula) AS funcionarios
FROM janelas AS j
LEFT JOIN vw_status_item AS i
    ON i.regra <> 'NÃO' AND i.dias_para_vencer BETWEEN 0 AND j.janela_dias
GROUP BY j.janela_dias
ORDER BY j.janela_dias;
