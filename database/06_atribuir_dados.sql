
-- ===========================================
-- MyFinance - Migração 06
-- Associar dados antigos ao usuário principal
-- ===========================================

BEGIN;

-- Confirma que o usuário principal existe
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM usuarios
        WHERE id = 2 AND ativo = TRUE
    ) THEN
        RAISE EXCEPTION 'Usuário 2 não encontrado ou inativo';
    END IF;
END;
$$;

-- Vincula movimentações antigas ao usuário 2
UPDATE transacoes
SET usuario_id = 2
WHERE usuario_id IS NULL;

-- Vincula contas fixas antigas ao usuário 2
UPDATE contas_fixas
SET usuario_id = 2
WHERE usuario_id IS NULL;

-- Verifica se algum registro continua sem proprietário
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM transacoes
        WHERE usuario_id IS NULL
    ) OR EXISTS (
        SELECT 1 FROM contas_fixas
        WHERE usuario_id IS NULL
    ) THEN
        RAISE EXCEPTION 'Existem registros sem proprietário';
    END IF;

    -- Impede que um pagamento vincule uma transação
    -- pertencente a outro usuário.
    IF EXISTS (
        SELECT 1
        FROM vencimentos v
        JOIN contas_fixas c ON c.id = v.conta_fixa_id
        JOIN transacoes t ON t.id = v.transacao_id
        WHERE c.usuario_id IS DISTINCT FROM t.usuario_id
    ) THEN
        RAISE EXCEPTION 'Existem pagamentos com proprietários diferentes';
    END IF;
END;
$$;

COMMIT;
