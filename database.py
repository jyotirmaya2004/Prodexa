import mysql.connector


# -----------------------------------
# Database Connection
# -----------------------------------
def connect_db():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="7205",
        database="prodexa"
    )


# -----------------------------------
# Create Table
# -----------------------------------
def create_products_table():
    conn = connect_db()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INT AUTO_INCREMENT PRIMARY KEY,
            username VARCHAR(100) UNIQUE NOT NULL,
            password_hash VARCHAR(255) NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT,
            source VARCHAR(100),
            source_url TEXT,
            search_url TEXT,
            product_name TEXT,
            price INT,
            description TEXT,
            image TEXT,
            link TEXT,
            brand VARCHAR(100),
            curated_at DATETIME,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """)

    for statement in [
        "ALTER TABLE products ADD COLUMN source_url TEXT",
        "ALTER TABLE products ADD COLUMN search_url TEXT",
        "ALTER TABLE products ADD COLUMN user_id INT",
        "ALTER TABLE products ADD CONSTRAINT fk_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE"
    ]:
        try:
            cursor.execute(statement)
        except mysql.connector.Error:
            pass

    conn.commit()
    conn.close()


# -----------------------------------
# Insert Products
# -----------------------------------
def insert_products(df, user_id=None):
    conn = connect_db()
    cursor = conn.cursor()

    query = """
        INSERT INTO products
        (user_id, source, source_url, search_url, product_name, price, description, image, link, brand, curated_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """

    for _, row in df.iterrows():
        values = (
            user_id,
            row["Source"],
            row.get("Source URL"),
            row.get("Search URL"),
            row["Product Name"],
            int(row["Price"]),
            row["Description"],
            row["Image"],
            row["Link"],
            row["Brand"],
            row["Curated At"]
        )

        cursor.execute(query, values)

    conn.commit()
    conn.close()


# -----------------------------------
# Fetch All Products
# -----------------------------------
def get_all_products(user_id=None):
    conn = connect_db()
    cursor = conn.cursor(dictionary=True)

    if user_id is not None:
        cursor.execute("SELECT * FROM products WHERE user_id = %s ORDER BY curated_at DESC, id DESC", (user_id,))
    else:
        cursor.execute("SELECT * FROM products ORDER BY curated_at DESC, id DESC")
    rows = cursor.fetchall()

    conn.close()

    return rows


# -----------------------------------
# Delete Product
# -----------------------------------
def delete_product(product_id, user_id=None):
    conn = connect_db()
    cursor = conn.cursor()

    if user_id is not None:
        cursor.execute(
            "DELETE FROM products WHERE id = %s AND user_id = %s",
            (product_id, user_id)
        )
    else:
        cursor.execute(
            "DELETE FROM products WHERE id = %s",
            (product_id,)
        )

    conn.commit()
    conn.close()


# -----------------------------------
# User Management
# -----------------------------------
def create_user(username, password_hash):
    conn = connect_db()
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO users (username, password_hash) VALUES (%s, %s)", (username, password_hash))
        conn.commit()
        return True
    except mysql.connector.Error:
        return False
    finally:
        conn.close()

def get_user_by_username(username):
    conn = connect_db()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
    user = cursor.fetchone()
    conn.close()
    return user
