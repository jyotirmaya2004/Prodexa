SELECT id, user_id, source, source_url, search_url, product_name, price, description, image, link, brand, curated_at, created_at
FROM products
WHERE user_id = %s
ORDER BY created_at DESC;