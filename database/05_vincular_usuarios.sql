
-- ===========================================
-- MyFinance - Migração 05
-- Preparação para múltiplos usuários
-- ===========================================

BEGIN;

-- Adicionar proprietário às transações
ALTER TABLE transacoes
ADD COLUMN IF NOT EXISTS usuario_id INTEGER
REFERENCES usuarios(id);

-- Adicionar proprietário às contas fixas
ALTER TABLE contas_fixas
ADD COLUMN IF NOT EXISTS usuario_id INTEGER
REFERENCES usuarios(id);

-- Índices para consultas por usuário
CREATE INDEX IF NOT EXISTS idx_transacoes_usuario
ON transacoes(usuario_id);

CREATE INDEX IF NOT EXISTS idx_contas_fixas_usuario
ON contas_fixas(usuario_id);

COMMIT;
