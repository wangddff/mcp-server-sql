import re
import logging
import os
from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.security import HTTPBearer
from pydantic import BaseModel
from typing import Any, Dict, List, Optional
import psycopg2
import pymysql

from config import DATABASE_URL, DB_TYPE, ALLOWED_TABLES, ALLOWED_COLUMNS, FORBIDDEN_KEYWORDS

app = FastAPI(title="MCP SQL Server", version="1.0")
security = HTTPBearer(auto_error=False)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

API_KEY = os.getenv("MCP_API_KEY")

def verify_token(credentials = Depends(security)):
    if API_KEY and (not credentials or credentials.credentials != API_KEY):
        raise HTTPException(status_code=403, detail="Invalid or missing API key")

# ======================
# MCP /manifest 端点（Dify 1.10.1 必需）
# ======================
@app.get("/manifest")
async def get_manifest():
    return {
        "name": "sql_database_query",
        "description": "Securely query PostgreSQL or MySQL databases using natural language.",
        "version": "1.0.0",
        "tools": [
            {
                "name": "query_database",
                "description": "Execute a SELECT SQL query against the allowed tables and return JSON results.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "sql": {
                            "type": "string",
                            "description": "A valid SELECT SQL statement (e.g., SELECT product_name, SUM(sale_amount) FROM sales GROUP BY product_name)"
                        }
                    },
                    "required": ["sql"]
                }
            }
        ]
    }

# ======================
# 工具调用端点：POST /query_database
# Dify 会直接 POST 到此路径（带 JSON body）
# ======================
class QueryParams(BaseModel):
    sql: str

@app.post("/query_database", dependencies=[Depends(verify_token) if API_KEY else Depends(lambda: None)])
async def handle_query_database(params: QueryParams, req: Request):
    client_ip = req.client.host
    logger.info(f"[MCP] {client_ip} → tool=query_database")

    sql = params.sql.strip()
    if not sql:
        raise HTTPException(status_code=400, detail="SQL cannot be empty")

    # --- 安全校验 ---
    sql_lower = sql.lower()
    if not sql_lower.startswith("select"):
        raise HTTPException(status_code=400, detail="Only SELECT queries allowed")
    
    for kw in FORBIDDEN_KEYWORDS:
        if kw in sql_lower:
            raise HTTPException(status_code=400, detail=f"Forbidden keyword: {kw}")
    
    from_match = re.search(r'\bfrom\s+([a-zA-Z_][a-zA-Z0-9_]*)', sql_lower)
    if from_match:
        table = from_match.group(1)
        if table not in ALLOWED_TABLES:
            raise HTTPException(status_code=400, detail=f"Table '{table}' is not allowed")

    # --- 执行查询 ---
    try:
        if DB_TYPE == "postgresql":
            conn = psycopg2.connect(DATABASE_URL)
        elif DB_TYPE == "mysql":
            import urllib.parse
            parsed = urllib.parse.urlparse(DATABASE_URL)
            conn = pymysql.connect(
                host=parsed.hostname,
                port=parsed.port or 3306,
                user=parsed.username,
                password=parsed.password,
                database=parsed.path[1:],
                charset='utf8mb4'
            )
        else:
            raise ValueError("Unsupported DB_TYPE")

        with conn.cursor() as cur:
            cur.execute(sql)
            columns = [desc[0] for desc in cur.description]
            rows = [dict(zip(columns, row)) for row in cur.fetchall()]
        conn.close()

        return {
            "data": rows,
            "count": len(rows)
        }

    except Exception as e:
        logger.error(f"Query error: {e}")
        raise HTTPException(status_code=500, detail=f"Database execution failed: {str(e)}")

# ======================
# 健康检查
# ======================
@app.get("/health")
def health():
    return {"status": "ok", "db_type": DB_TYPE}
