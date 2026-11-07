-- Agenda de reciclagem: cada item que vence entre hoje e o fim da maior janela,
-- em ordem de vencimento. É a terceira página do painel.
SELECT
    data_vencimento,
    dias_para_vencer,
    matricula,
    nome,
    funcao,
    equipe,
    treinamento,
    regra,
    status
FROM vw_status_item
WHERE regra <> 'NÃO'
  AND dias_para_vencer BETWEEN 0 AND (SELECT janela_3 FROM parametro)
ORDER BY data_vencimento, matricula, treinamento;
