SELECT id, username, email, password_hash
FROM users
WHERE LOWER(email) = LOWER(%s);
