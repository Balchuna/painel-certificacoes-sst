-- Visão geral na data de referência: os cartões da primeira página do painel.
-- Conformidade conta só itens obrigatórios (SIM). "itens_vencidos" conta também
-- os CONDICIONAIS que têm data e venceram; NÃO fica fora de tudo.
SELECT
    (SELECT data_referencia FROM parametro) AS data_referencia,
    COUNT(DISTINCT matricula) AS funcionarios_ativos,
    COUNT(DISTINCT CASE WHEN pendente = 1 THEN matricula END) AS funcionarios_irregulares,
    SUM(obrigatorio) AS itens_obrigatorios,
    SUM(obrigatorio) - SUM(pendente) AS itens_validos,
    ROUND(100.0 * (SUM(obrigatorio) - SUM(pendente)) / SUM(obrigatorio), 1) AS pct_conformidade,
    SUM(pendente) AS pendentes_obrigatorios,
    SUM(CASE WHEN pendente = 1 AND status = 'Sem registro' THEN 1 ELSE 0 END)
        AS obrigatorios_sem_registro,
    SUM(CASE WHEN pendente = 1 AND status = 'Vencido' THEN 1 ELSE 0 END) AS obrigatorios_vencidos,
    SUM(CASE WHEN status = 'Vencido' THEN 1 ELSE 0 END) AS itens_vencidos
FROM vw_status_item;
