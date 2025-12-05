import logging
import json
import psycopg2
import pymysql
import urllib.parse
from typing import Any, List, Dict
from fastmcp import FastMCP
from config import DATABASE_URL, DB_TYPE, ALLOWED_TABLES, FORBIDDEN_KEYWORDS

# 初始化 FastMCP 服务
# dependencies 列表可以用来注入依赖，这里我们简单起见直接使用
mcp = FastMCP(
    "SQL Server",
    host="0.0.0.0",
    port=8000
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def validate_sql(sql: str) -> None:
    """验证 SQL 安全性 (保留原有逻辑)"""
    sql_lower = sql.lower().strip()
    if not sql_lower.startswith("select"):
        raise ValueError("Only SELECT queries allowed")
    
    for kw in FORBIDDEN_KEYWORDS:
        if kw in sql_lower:
            raise ValueError(f"Forbidden keyword: {kw}")
    
    # 简单的表名检查 (建议生产环境使用更严格的解析库)
    import re
    from_match = re.search(r'\bfrom\s+([a-zA-Z_][a-zA-Z0-9_]*)', sql_lower)
    if from_match:
        table = from_match.group(1)
        if table not in ALLOWED_TABLES:
            raise ValueError(f"Table '{table}' not allowed")

def get_connection():
    """获取数据库连接"""
    if DB_TYPE == "postgresql":
        return psycopg2.connect(DATABASE_URL)
    elif DB_TYPE == "mysql":
        parsed = urllib.parse.urlparse(DATABASE_URL)
        return pymysql.connect(
            host=parsed.hostname,
            port=parsed.port or 3306,
            user=parsed.username,
            password=parsed.password,
            database=parsed.path[1:],
            charset='utf8mb4'
        )
    else:
        raise ValueError(f"Unsupported DB_TYPE: {DB_TYPE}")

@mcp.tool()
def query_database(sql: str) -> str:
    """
    Execute a read-only SQL query against the connected database.
    
    Args:
        sql: The SQL SELECT statement to execute. 
             Make sure to use correct syntax for the underlying database (PostgreSQL or MySQL).
    """
    logger.info(f"[MCP] Executing SQL: {sql}")
    
    try:
        validate_sql(sql)
        
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(sql)
                # 获取列名
                if cur.description:
                    columns = [desc[0] for desc in cur.description]
                    rows = [dict(zip(columns, row)) for row in cur.fetchall()]
                else:
                    return "Query executed successfully but returned no results."
                
                # 返回 JSON 字符串，这对 LLM 来说最容易解析
                return json.dumps(rows, ensure_ascii=False, default=str)
        finally:
            conn.close()
            
    except Exception as e:
        logger.error(f"Query failed: {e}")
        # 直接返回错误信息给 LLM，让它知道 SQL 哪里错了
        return f"Error executing query: {str(e)}"

# 启动入口
# FastMCP 默认使用 SSE 传输模式，适合 Dify 通过 HTTP 调用
if __name__ == "__main__":
    mcp.run(transport="sse")
