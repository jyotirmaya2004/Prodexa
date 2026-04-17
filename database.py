
# -----------------------------------
# Database Connection
# -----------------------------------
import os
import psycopg2
import psycopg2.extras

def connect_db():
    """Connect to the database.

    Resolution order:
    1. DATABASE_URL environment variable (Supabase standard connection string)
    2. Individual env vars: DB_HOST, DB_USER, DB_PASSWORD, DB_NAME, DB_PORT
    3. Hardcoded Supabase credentials as last resort

    DNS resolution is left entirely to psycopg2 so that both IPv4 and IPv6
    records are handled transparently by the OS resolver.
    """
    database_url = os.environ.get("DATABASE_URL")

    try:
        if database_url:
            conn = psycopg2.connect(
                database_url,
                sslmode="require",
                connect_timeout=10,
            )
        else:
            host = os.environ.get("DB_HOST", "aws-1-ap-south-1.pooler.supabase.com")
            user = os.environ.get("DB_USER", "postgres.mlypbdgaqhvcwsvqvseu")
            password = os.environ.get("DB_PASSWORD", "f0AZrCitkFSL62IB")
            dbname = os.environ.get("DB_NAME", "postgres")
            port = int(os.environ.get("DB_PORT", 5432))

            conn = psycopg2.connect(
                host=host,
                database=dbname,
                user=user,
                password=password,
                port=port,
                sslmode="require",
                connect_timeout=10,
            )

        return conn
    except psycopg2.Error as e:
        print(f"❌ Database connection error: {e}")
        raise

def get_sql_query(filename):
    base_dir = os.path.dirname(os.path.abspath(__file__))
    filepath = os.path.join(base_dir, 'sql', filename)
    with open(filepath, 'r') as file:
        return file.read()


# -----------------------------------
# Insert Products
# -----------------------------------
def insert_products(df, user_id=None):
    conn = connect_db()
    cursor = conn.cursor()

    query = get_sql_query('insert_product.sql')

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
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    if user_id is not None:
        query = get_sql_query('get_products_by_user.sql')
        cursor.execute(query, (user_id,))
    else:
        query = get_sql_query('get_all_products.sql')
        cursor.execute(query)
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
        query = get_sql_query('delete_product_by_user.sql')
        cursor.execute(query, (product_id, user_id))
    else:
        query = get_sql_query('delete_product.sql')
        cursor.execute(query, (product_id,))

    conn.commit()
    conn.close()


# -----------------------------------
# User Management
# -----------------------------------
def create_user(username, password_hash):
    conn = connect_db()
    cursor = conn.cursor()
    try:
        query = get_sql_query('insert_user.sql')
        cursor.execute(query, (username, password_hash))
        conn.commit()
        return True
    except psycopg2.Error:
        conn.rollback()
        return False
    finally:
        conn.close()

def get_user_by_username(username):
    conn = connect_db()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    query = get_sql_query('get_user_by_username.sql')
    cursor.execute(query, (username,))
    user = cursor.fetchone()
    conn.close()
    return user

# -----------------------------------
# Database Initialization & Test
# -----------------------------------
if __name__ == "__main__":
    print("Testing database connection...")
    try:
        conn = connect_db()
        print("✅ Successfully connected to the database!")
        conn.close()
    except Exception as e:
        print(f"❌ Failed to connect to the database.\nDetails: {e}")
