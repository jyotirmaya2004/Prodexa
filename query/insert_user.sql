INSERT INTO users (username, email, password_hash)
VALUES (%s, %s, %s)
RETURNING id, username, email, password_hash;
