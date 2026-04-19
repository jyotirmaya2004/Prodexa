
# -----------------------------------
# Database Connection
# -----------------------------------
import os
from datetime import datetime, timedelta, timezone

import psycopg2
import psycopg2.extras
from dotenv import load_dotenv


load_dotenv()

_AUTH_SCHEMA_READY = False


def connect_db():
    """Connect to the database.

    Resolution order:
    1. DATABASE_URL environment variable (Supabase standard connection string)
    2. Individual env vars: DB_HOST, DB_USER, DB_PASSWORD, DB_NAME, DB_PORT
    3. Hardcoded Supabase credentials as last resort
    """
    database_url = os.environ.get("DATABASE_URL")
    sslmode = os.environ.get("DB_SSLMODE", "require")

    try:
        if database_url:
            conn = psycopg2.connect(
                database_url,
                sslmode=sslmode,
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
                sslmode=sslmode,
                connect_timeout=10,
            )

        return conn
    except psycopg2.Error as e:
        print(f"Database connection error: {e}")
        raise


def ensure_auth_schema():
    global _AUTH_SCHEMA_READY
    if _AUTH_SCHEMA_READY:
        return

    conn = connect_db()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            ALTER TABLE users
            ADD COLUMN IF NOT EXISTS email TEXT
            """
        )
        cursor.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS users_email_unique_idx
            ON users (LOWER(email))
            WHERE email IS NOT NULL
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS password_reset_codes (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                code_hash TEXT NOT NULL,
                expires_at TIMESTAMPTZ NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                used_at TIMESTAMPTZ
            )
            """
        )
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS password_reset_codes_user_id_idx
            ON password_reset_codes (user_id, created_at DESC)
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS abuse_ip_blocks (
                ip_address TEXT PRIMARY KEY,
                violations INTEGER NOT NULL DEFAULT 0,
                window_started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                last_violation_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                blocked_until TIMESTAMPTZ,
                reason TEXT,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        )
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS abuse_ip_blocks_blocked_until_idx
            ON abuse_ip_blocks (blocked_until)
            """
        )
        conn.commit()
        _AUTH_SCHEMA_READY = True
    except psycopg2.Error:
        conn.rollback()
        raise
    finally:
        conn.close()


def get_sql_query(filename):
    base_dir = os.path.dirname(os.path.abspath(__file__))
    filepath = os.path.join(base_dir, "query", filename)
    with open(filepath, "r", encoding="utf-8") as file:
        return file.read()


# -----------------------------------
# Insert Products
# -----------------------------------
def insert_products(df, user_id=None):
    conn = connect_db()
    cursor = conn.cursor()

    query = get_sql_query("insert_product.sql")

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
            row["Curated At"],
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
        query = get_sql_query("get_products_by_user.sql")
        cursor.execute(query, (user_id,))
    else:
        query = get_sql_query("get_all_products.sql")
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
        query = get_sql_query("delete_product_by_user.sql")
        cursor.execute(query, (product_id, user_id))
    else:
        query = get_sql_query("delete_product.sql")
        cursor.execute(query, (product_id,))

    conn.commit()
    conn.close()


# -----------------------------------
# User Management
# -----------------------------------
def create_user(username, email, password_hash):
    ensure_auth_schema()
    conn = connect_db()
    cursor = conn.cursor()
    try:
        query = get_sql_query("insert_user.sql")
        cursor.execute(query, (username, email, password_hash))
        conn.commit()
        return True
    except psycopg2.Error:
        conn.rollback()
        return False
    finally:
        conn.close()


def get_user_by_username(username):
    ensure_auth_schema()
    conn = connect_db()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    query = get_sql_query("get_user_by_username.sql")
    cursor.execute(query, (username,))
    user = cursor.fetchone()
    conn.close()
    return user


def get_user_by_email(email):
    ensure_auth_schema()
    conn = connect_db()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    query = get_sql_query("get_user_by_email.sql")
    cursor.execute(query, (email,))
    user = cursor.fetchone()
    conn.close()
    return user


def store_password_reset_code(user_id, code_hash, expires_at):
    ensure_auth_schema()
    conn = connect_db()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            UPDATE password_reset_codes
            SET used_at = NOW()
            WHERE user_id = %s AND used_at IS NULL
            """,
            (user_id,),
        )
        cursor.execute(
            """
            INSERT INTO password_reset_codes (user_id, code_hash, expires_at)
            VALUES (%s, %s, %s)
            """,
            (user_id, code_hash, expires_at),
        )
        conn.commit()
        return True
    except psycopg2.Error:
        conn.rollback()
        return False
    finally:
        conn.close()


def get_latest_active_reset_code(user_id):
    ensure_auth_schema()
    conn = connect_db()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cursor.execute(
        """
        SELECT id, user_id, code_hash, expires_at, created_at, used_at
        FROM password_reset_codes
        WHERE user_id = %s
          AND used_at IS NULL
          AND expires_at > NOW()
        ORDER BY created_at DESC
        LIMIT 1
        """,
        (user_id,),
    )
    row = cursor.fetchone()
    conn.close()
    return row


def mark_password_reset_code_used(reset_code_id):
    ensure_auth_schema()
    conn = connect_db()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            UPDATE password_reset_codes
            SET used_at = NOW()
            WHERE id = %s
            """,
            (reset_code_id,),
        )
        conn.commit()
        return True
    except psycopg2.Error:
        conn.rollback()
        return False
    finally:
        conn.close()


def update_user_password(user_id, password_hash):
    ensure_auth_schema()
    conn = connect_db()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            UPDATE users
            SET password_hash = %s
            WHERE id = %s
            """,
            (password_hash, user_id),
        )
        conn.commit()
        return True
    except psycopg2.Error:
        conn.rollback()
        return False
    finally:
        conn.close()


def get_active_ip_block(ip_address):
    ensure_auth_schema()
    conn = connect_db()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cursor.execute(
        """
        SELECT ip_address, violations, blocked_until, reason, updated_at
        FROM abuse_ip_blocks
        WHERE ip_address = %s
          AND blocked_until IS NOT NULL
          AND blocked_until > NOW()
        LIMIT 1
        """,
        (ip_address,),
    )
    row = cursor.fetchone()
    conn.close()
    return row


def record_ip_violation(ip_address, max_violations, window_seconds, block_seconds, reason="abuse"):
    ensure_auth_schema()
    now = datetime.now(timezone.utc)

    conn = connect_db()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        cursor.execute(
            """
            SELECT ip_address, violations, window_started_at, blocked_until
            FROM abuse_ip_blocks
            WHERE ip_address = %s
            FOR UPDATE
            """,
            (ip_address,),
        )
        row = cursor.fetchone()

        violations = 1
        window_started_at = now
        blocked_until = None

        if row:
            prior_window_start = row.get("window_started_at") or now
            elapsed = (now - prior_window_start).total_seconds()
            if elapsed <= max(window_seconds, 1):
                violations = int(row.get("violations") or 0) + 1
                window_started_at = prior_window_start

        if violations >= max(max_violations, 1):
            blocked_until = now + timedelta(seconds=max(block_seconds, 1))

        if row:
            cursor.execute(
                """
                UPDATE abuse_ip_blocks
                SET violations = %s,
                    window_started_at = %s,
                    last_violation_at = %s,
                    blocked_until = %s,
                    reason = %s,
                    updated_at = NOW()
                WHERE ip_address = %s
                """,
                (violations, window_started_at, now, blocked_until, reason, ip_address),
            )
        else:
            cursor.execute(
                """
                INSERT INTO abuse_ip_blocks (
                    ip_address,
                    violations,
                    window_started_at,
                    last_violation_at,
                    blocked_until,
                    reason
                )
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (ip_address, violations, window_started_at, now, blocked_until, reason),
            )

        conn.commit()
        return {
            "ip_address": ip_address,
            "violations": violations,
            "blocked_until": blocked_until,
        }
    except psycopg2.Error:
        conn.rollback()
        return None
    finally:
        conn.close()


# -----------------------------------
# Database Initialization & Test
# -----------------------------------
if __name__ == "__main__":
    print("Testing database connection...")
    try:
        conn = connect_db()
        conn.close()
        ensure_auth_schema()
        print("Successfully connected to the database!")
    except Exception as e:
        print(f"Failed to connect to the database.\nDetails: {e}")
