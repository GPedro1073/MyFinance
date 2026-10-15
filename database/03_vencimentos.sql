
-- MyFinance - Migração 03
-- Controle de vencimentos e pagamentos

BEGIN;

CREATE TABLE vencimentos (
    id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    conta_fixa_id INTEGER NOT NULL
        REFERENCES contas_fixas(id),

    competencia DATE NOT NULL,

    data_vencimento DATE NOT NULL,

    descricao VARCHAR(150) NOT NULL,

    valor NUMERIC(12, 2) NOT NULL
        CHECK (valor > 0),

    categoria_id INTEGER NOT NULL
        REFERENCES categorias(id),

    transacao_id INTEGER UNIQUE
        REFERENCES transacoes(id),

    criado_em TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_conta_competencia
        UNIQUE (conta_fixa_id, competencia),

    CONSTRAINT chk_competencia_inicio
        CHECK (
            EXTRACT(DAY FROM competencia) = 1
        )
);

CREATE INDEX idx_vencimentos_competencia
    ON vencimentos(competencia);

CREATE INDEX idx_vencimentos_data
    ON vencimentos(data_vencimento);

COMMIT;

