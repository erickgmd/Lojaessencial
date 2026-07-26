-- Execute no Supabase SQL Editor uma única vez.

alter table public.category
  add column if not exists image_url varchar(700) default '',
  add column if not exists image_path varchar(500) default '';

-- Bucket público para imagens das categorias.
insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values (
  'category-images',
  'category-images',
  true,
  15728640,
  array['image/png', 'image/jpeg', 'image/webp']
)
on conflict (id) do update set
  public = excluded.public,
  file_size_limit = excluded.file_size_limit,
  allowed_mime_types = excluded.allowed_mime_types;

-- A leitura pública é necessária para as imagens aparecerem no catálogo.
drop policy if exists "Public read category images" on storage.objects;
create policy "Public read category images"
on storage.objects for select
to public
using (bucket_id = 'category-images');

-- Upload, atualização e exclusão são feitos no backend com a Service Role Key.
-- Portanto, não é necessária uma policy pública de escrita.
