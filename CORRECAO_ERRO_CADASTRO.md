# Correção do erro ao cadastrar produto

Esta versão trata os erros sem exibir apenas “Internal Server Error”.

Ela também cria automaticamente, caso ainda não existam, as colunas:

- `product_image.path`
- `category.image_url`
- `category.image_path`

Após enviar esta versão ao GitHub, faça um novo deploy no Render.

Se o Render não iniciar por falta de permissão para alterar tabelas, execute no SQL Editor do Supabase:

```sql
ALTER TABLE product_image ADD COLUMN IF NOT EXISTS path VARCHAR(500) DEFAULT '';
ALTER TABLE category ADD COLUMN IF NOT EXISTS image_url VARCHAR(700) DEFAULT '';
ALTER TABLE category ADD COLUMN IF NOT EXISTS image_path VARCHAR(500) DEFAULT '';
```

Confirme também as variáveis no Render:

- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY`
- `SUPABASE_PRODUCT_BUCKET=product-images`
- `SUPABASE_CATEGORY_BUCKET=category-images`
