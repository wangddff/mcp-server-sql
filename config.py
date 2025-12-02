import os
from typing import Set

DATABASE_URL = os.getenv("DATABASE_URL", "")
DB_TYPE = os.getenv("DB_TYPE", "postgresql").lower()

# ⚠️ MODIFY THESE TO MATCH YOUR SCHEMA
ALLOWED_TABLES: Set[str] = {"sales", "users", "products", "orders"}
ALLOWED_COLUMNS: Set[str] = {
    "id", "name", "email", "product_name", "sale_amount",
    "order_date", "customer_id", "created_at", "status"
}

FORBIDDEN_KEYWORDS = {
    "drop", "delete", "update", "insert", "create", "alter",
    "exec", "execute", "union", "load_file", "information_schema",
    "pg_", "mysql.", "sqlite_", "sys.", "schema", "table"
}
