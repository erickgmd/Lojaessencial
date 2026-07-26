# Essencial

Catálogo de roupas em Flask, PostgreSQL/Supabase e Supabase Storage.

## Arquivos principais

- `app.py`: aplicação Flask
- `create_admin.py`: cria o primeiro administrador
- `render.yaml`: configuração de deploy no Render
- `supabase_schema.sql`: estrutura inicial do banco
- `supabase_migration_*.sql`: atualizações para bancos existentes

## Executar localmente

```bash
python -m venv .venv
pip install -r requirements.txt
```

Copie `.env.example` para `.env`, preencha as variáveis e execute:

```bash
python app.py
```

Para criar o administrador:

```bash
python create_admin.py
```

## Publicar no Render

1. Envie esta pasta para um repositório do GitHub.
2. No Render, crie um **Blueprint** usando o repositório.
3. O Render detectará o arquivo `render.yaml`.
4. Preencha as variáveis marcadas como secretas.
5. Após o primeiro deploy, abra o Shell do serviço e execute `python create_admin.py`.

Nunca envie o arquivo `.env` nem a chave `SUPABASE_SERVICE_ROLE_KEY` ao GitHub.
