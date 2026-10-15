
-- Categorias iniciais
INSERT INTO categorias (nome) VALUES
('Alimentação'),
('Transporte'),
('Moradia'),
('Educação'),
('Lazer'),
('Assinaturas'),
('Salário'),
('Outros');

-- Transações fictícias de outubro de 2026
INSERT INTO transacoes
(descricao, valor, tipo, data_transacao, categoria_id)
VALUES
('Salário', 2500.00, 'receita', '2026-10-05', 7),
('Supermercado', 185.90, 'despesa', '2026-10-07', 1),
('Combustível', 120.00, 'despesa', '2026-10-08', 2),
('Cinema', 45.00, 'despesa', '2026-10-10', 5),
('Streaming', 39.90, 'despesa', '2026-10-12', 6);

-- Contas recorrentes fictícias
INSERT INTO contas_fixas
(descricao, valor, dia_vencimento, categoria_id)
VALUES
('Internet', 100.00, 10, 3),
('Faculdade', 800.00, 15, 4),
('Streaming', 39.90, 12, 6);
