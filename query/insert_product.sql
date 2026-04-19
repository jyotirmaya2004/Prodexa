INSERT INTO products (user_id, source, source_url, search_url, product_name, price, description, image, link, brand, curated_at)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
RETURNING id, product_name, price;
