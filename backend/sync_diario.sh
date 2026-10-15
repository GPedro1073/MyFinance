
#!/bin/bash

# Entrar na pasta do MyFinance
cd "$HOME/projetos/myfinance/backend" || exit 1

# Descobrir o mês e ano atuais
ANO=$(date +%Y)
MES=$(date +%m)

# Executar sincronização
"$HOME/projetos/myfinance/backend/.venv/bin/python" \
    notion_upsert.py "$ANO" "$MES"
