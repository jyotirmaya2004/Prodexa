SELECT id, user_id, source, source_url, search_url, product_name, price, description, image, link, brand, curated_at
FROM products
WHERE user_id = %s
ORDER BY curated_at DESC;
