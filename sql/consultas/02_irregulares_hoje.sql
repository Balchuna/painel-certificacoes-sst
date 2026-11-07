-- Quem está irregular hoje: funcionários ativos com pelo menos um item
-- obrigatório sem registro ou vencido. Os mais pendentes primeiro.
SELECT
    matricula,
    nome,
    funcao,
    equipe,
    COUNT(*) AS pendencias,
    SUM(CASE WHEN motivo = 'Sem registro' THEN 1 ELSE 0 END) AS sem_registro,
    SUM(CASE WHEN motivo = 'Vencido' THEN 1 ELSE 0 END) AS vencidos,
    -- group_concat com ORDER BY pede SQLite 3.44 ou mais novo.
    group_concat(treinamento, ', ' ORDER BY treinamento) AS treinamentos
FROM vw_pendencias_obrigatorias
GROUP BY matricula, nome, funcao, equipe
ORDER BY pendencias DESC, matricula;
