
-- ===========================================
-- MyFinance - Sistema de usuários
-- Migração 04
-- ===========================================

CREATE TABLE IF NOT EXISTS usuarios (
    id INTEGER GENERATED ALWAYS AS IDENTITY
        PRIMARY KEY,

    nome VARCHAR(120) NOT NULL,

    email VARCHAR(255) NOT NULL,

    senha_hash TEXT NOT NULL,

    ativo BOOLEAN NOT NULL DEFAULT TRUE,

    criado_em TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Impede cadastros com o mesmo email
-- ignorando diferenças entre maiúsculas e minúsculas.

CREATE UNIQUE INDEX IF NOT EXISTS
    idx_usuarios_email
ON usuarios (LOWER(email));
