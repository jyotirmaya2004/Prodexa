INSERT INTO users (username, password_hash, created_at)
VALUES (%s, %s, NOW())
RETURNING id, username, password_hash;