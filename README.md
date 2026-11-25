# MyFinance

[Português](#português) · [English](#english)

## Português

O MyFinance é um gerenciador financeiro pessoal para registrar receitas e despesas, acompanhar contas fixas e seus pagamentos, consultar relatórios mensais e exportar resumos para o Notion.

### Arquitetura e estrutura

O navegador carrega HTML, CSS e JavaScript servidos pelo FastAPI e consulta a API na mesma origem. O backend usa Python, Pydantic para validação e Psycopg para executar SQL parametrizado no PostgreSQL. Uvicorn serve a aplicação. A autenticação usa JWT e senhas com hash Argon2. Os gráficos usam Chart.js via CDN, e os scripts de exportação usam HTTPX.

| Diretório | Conteúdo |
| --- | --- |
| `backend/` | API, autenticação, pagamentos, acesso ao banco, manifesto de dependências e scripts do Notion |
| `backend/tests/` | Testes de inicialização e autenticação com banco simulado |
| `database/` | Esquema, dados de exemplo e scripts históricos de evolução |
| `frontend/` | Interface, estilos e JavaScript |

Cadastro e login permanecem públicos. As rotas financeiras exigem o JWT no cabeçalho `Authorization: Bearer <token>`. O catálogo de categorias é global e somente leitura. A interface atual ainda não envia o token, portanto suas operações financeiras retornam HTTP 401 até a MF-004. Para desenvolvimento, faça login e teste a API por `/docs` ou por um cliente HTTP.

O banco precisa das colunas `usuario_id` criadas pelo script `05_vincular_usuarios.sql`. Registros sem dono e vencimentos com pagamentos de titularidade inconsistente ficam fora dos fluxos da API até a reconciliação. A MF-005 tratará atribuição legada e restrições permanentes.

### Instalação e execução

Use Python 3.12 e um PostgreSQL de desenvolvimento. Execute a partir da raiz do repositório. Copie o arquivo de exemplo apenas na primeira configuração.

**Windows (PowerShell)**

```powershell
python -m venv backend\.venv
.\backend\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
Copy-Item backend\.env.example backend\.env
```

**Ubuntu 24.04 no WSL (Bash)**

```bash
python3 -m venv backend/.venv
backend/.venv/bin/python -m pip install -r backend/requirements.txt
cp -n backend/.env.example backend/.env
```

No `backend/.env`, configure o banco local e preencha `JWT_SECRET_KEY` com um valor aleatório exclusivo da instalação. Para gerar a chave, execute `python -c "import secrets; print(secrets.token_urlsafe(32))"` com o interpretador do ambiente virtual. Mantenha o arquivo fora do Git. Variáveis já definidas no processo têm precedência sobre o arquivo.

Depois de configurar o banco, execute na raiz:

```powershell
.\backend\.venv\Scripts\python.exe -m uvicorn main:app --app-dir backend --host 127.0.0.1 --port 8000
```

```bash
backend/.venv/bin/python -m uvicorn main:app --app-dir backend --host 127.0.0.1 --port 8000
```

Abra `http://127.0.0.1:8000/app` para a interface e `http://127.0.0.1:8000/docs` para a documentação da API.

### PostgreSQL

Crie um banco vazio de desenvolvimento e um papel de acesso local que possa criar as tabelas nesse banco. Informe `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER` e, quando exigida pelo PostgreSQL, `DB_PASSWORD`. No WSL, use o endereço alcançável a partir da distribuição onde a API está rodando. `127.0.0.1` é apropriado quando a API e o banco compartilham o mesmo ambiente de rede.

Para inicializar **apenas um banco novo de desenvolvimento**, execute com `psql` ou pgAdmin, na ordem, `01_schema.sql`, `03_vencimentos.sql`, `04_usuarios.sql` e `05_vincular_usuarios.sql`. `02_dados_teste.sql` é opcional e pode ser aplicado por último para popular exemplos. O script histórico `06_atribuir_dados.sql` altera titularidade legada e depende de um ID fixo. Antes de qualquer uso em uma base existente, revise o estado do esquema e a atribuição de cada registro.

### Notion

A integração é opcional. Para configurar o exportador, crie uma integração no Notion, dê acesso à página pai apropriada e configure `NOTION_TOKEN` e `NOTION_PAGE_ID` no ambiente do processo ou em `backend/.env`. Com `backend/` como diretório atual, `notion_upsert.py ANO MES` usa o interpretador do ambiente virtual para gravar o relatório mensal na página de destino. `sync_diario.sh` é o lançador Bash legado, com caminho fixo para o checkout original. Um agendamento deve apontar explicitamente para a cópia e o ambiente corretos. A exportação atual agrega dados da base toda. Use apenas com um banco de desenvolvimento ou uma base de usuário único com destino autorizado.

### Testes

Na raiz, execute `python -m unittest discover -s backend/tests -v` com o interpretador do ambiente virtual. Os testes usam uma chave fictícia, TestClient e mocks de banco. A suíte roda sem PostgreSQL ou Notion.

## English

MyFinance is a personal finance manager for recording income and expenses, tracking recurring bills and payments, viewing monthly reports, and exporting summaries to Notion.

### Architecture and layout

The browser loads HTML, CSS, and JavaScript served by FastAPI and calls the API on the same origin. The backend uses Python, Pydantic for validation, and Psycopg to execute parameterized SQL in PostgreSQL. Uvicorn serves the application. Authentication uses JWT and Argon2 password hashes. Charts use Chart.js from a CDN, and export scripts use HTTPX.

| Directory | Contents |
| --- | --- |
| `backend/` | API, authentication, payments, database access, dependency manifest, and Notion scripts |
| `backend/tests/` | Startup and authentication tests with a mocked database |
| `database/` | Schema, sample data, and historical upgrade scripts |
| `frontend/` | Interface, styles, and JavaScript |

Registration and login remain public. Financial endpoints require a JWT in the `Authorization: Bearer <token>` header. The category catalog is global and read-only. The current interface does not send the token, so its financial requests receive HTTP 401 until MF-004. For development, log in and test the API through `/docs` or an HTTP client.

The database must have the `usuario_id` columns created by `05_vincular_usuarios.sql`. Ownerless records and bills linked to payments with inconsistent ownership are excluded from the applicable API flows until reconciliation. MF-005 will address legacy ownership and permanent database constraints.

### Installation and startup

Use Python 3.12 and a development PostgreSQL instance. Run the commands from the repository root. Copy the example file during first-time setup only.

**Windows (PowerShell)**

```powershell
python -m venv backend\.venv
.\backend\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
Copy-Item backend\.env.example backend\.env
```

**Ubuntu 24.04 on WSL (Bash)**

```bash
python3 -m venv backend/.venv
backend/.venv/bin/python -m pip install -r backend/requirements.txt
cp -n backend/.env.example backend/.env
```

In `backend/.env`, configure the local database and set `JWT_SECRET_KEY` to a unique random value for the installation. To generate a key, run `python -c "import secrets; print(secrets.token_urlsafe(32))"` with the virtual environment interpreter. Keep the file out of Git. Existing process environment variables override the file.

After configuring the database, run from the repository root:

```powershell
.\backend\.venv\Scripts\python.exe -m uvicorn main:app --app-dir backend --host 127.0.0.1 --port 8000
```

```bash
backend/.venv/bin/python -m uvicorn main:app --app-dir backend --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000/app` for the interface and `http://127.0.0.1:8000/docs` for the API documentation.

### PostgreSQL

Create an empty development database and a local role that can create tables in it. Set `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, and `DB_PASSWORD` if PostgreSQL requires one. On WSL, use the address reachable from the distribution running the API. `127.0.0.1` works when the API and database share the same network environment.

To initialize **a new development database only**, use `psql` or pgAdmin to run `01_schema.sql`, `03_vencimentos.sql`, `04_usuarios.sql`, and `05_vincular_usuarios.sql` in that order. Optionally run `02_dados_teste.sql` last to add sample records. The historical `06_atribuir_dados.sql` changes legacy record ownership and depends on a fixed user ID. Review the schema state and record ownership before considering it for an existing database.

### Notion

The integration is optional. Create a Notion integration, grant access to the appropriate parent page, and set `NOTION_TOKEN` and `NOTION_PAGE_ID` in the process environment or `backend/.env`. From `backend/`, run `notion_upsert.py YEAR MONTH` with the virtual environment interpreter to write the monthly report to the destination page. `sync_diario.sh` is the legacy Bash launcher and assumes the original checkout path. Scheduled runs should point explicitly to the intended checkout and environment. The current export aggregates the entire database. Use it only with a development or single-user database and an authorized destination.

### Tests

From the repository root, run `python -m unittest discover -s backend/tests -v` with the virtual environment interpreter. The tests use a fictitious key, TestClient, and database mocks. The suite runs without PostgreSQL or Notion.
