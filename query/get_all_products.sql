SELECT id, user_id, source, source_url, search_url, product_name, price, description, image, link, brand, curated_at, created_at
FROM products
ORDER BY created_at DESC;