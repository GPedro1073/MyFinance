
-- ===========================================
-- MyFinance - Estrutura do banco de dados
-- ===========================================

-- 1. CATEGORIAS
CREATE TABLE categorias (
    id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    nome VARCHAR(80) NOT NULL UNIQUE
);

-- 2. TRANSACOES
CREATE TABLE transacoes (
    id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    descricao VARCHAR(150) NOT NULL,
    valor NUMERIC(12, 2) NOT NULL CHECK (valor > 0),
    tipo VARCHAR(10) NOT NULL
        CHECK (tipo IN ('receita', 'despesa')),
    data_transacao DATE NOT NULL,
    categoria_id INTEGER NOT NULL
        REFERENCES categorias(id),
    observacao TEXT,
    criado_em TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 3. CONTAS FIXAS
CREATE TABLE contas_fixas (
    id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    descricao VARCHAR(150) NOT NULL,
    valor NUMERIC(12, 2) NOT NULL CHECK (valor > 0),
    dia_vencimento INTEGER NOT NULL
        CHECK (dia_vencimento BETWEEN 1 AND 31),
    categoria_id INTEGER NOT NULL
        REFERENCES categorias(id),
    ativa BOOLEAN NOT NULL DEFAULT TRUE,
    criado_em TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Índices para agilizar consultas futuras
CREATE INDEX idx_transacoes_data
    ON transacoes(data_transacao);

CREATE INDEX idx_transacoes_categoria
    ON transacoes(categoria_id);
