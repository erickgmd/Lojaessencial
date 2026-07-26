-- Galeria de imagens dos produtos
ALTER TABLE public.product_image
    ADD COLUMN IF NOT EXISTS is_primary BOOLEAN NOT NULL DEFAULT FALSE;

ALTER TABLE public.product_image
    ADD COLUMN IF NOT EXISTS sort_order INTEGER NOT NULL DEFAULT 0;

-- Define uma imagem principal para produtos antigos que ainda não tenham uma.
WITH first_images AS (
    SELECT DISTINCT ON (product_id) id
    FROM public.product_image
    ORDER BY product_id, sort_order, id
)
UPDATE public.product_image AS image
SET is_primary = TRUE
FROM first_images
WHERE image.id = first_images.id
  AND NOT EXISTS (
      SELECT 1
      FROM public.product_image AS existing
      WHERE existing.product_id = image.product_id
        AND existing.is_primary = TRUE
  );
