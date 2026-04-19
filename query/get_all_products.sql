SELECT id, user_id, source, source_url, search_url, product_name, price, description, image, link, brand, curated_at
FROM products
ORDER BY curated_at DESC;
