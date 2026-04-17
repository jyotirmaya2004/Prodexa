INSERT INTO products (user_id, source, source_url, search_url, product_name, price, description, image, link, brand, curated_at, created_at)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
RETURNING id, product_name, price;