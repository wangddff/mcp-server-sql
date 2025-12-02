import re
import logging
import os
import json
from decimal import Decimal
from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.security import HTTPBearer
from fastapi.responses import StreamingResponse
from sse_starlette.sse import EventSourceResponse
from pydantic import BaseModel
from typing import Any, Dict, Optional
import psycopg2
import pymysql
from config import DATABASE_URL, DB_TYPE, ALLOWED_TABLES, FORBIDDEN_KEYWORDS


class DecimalEncoder(json.JSONEncoder):
  def default(self, o):
    if isinstance(o, Decimal):
      return float(o)
    return super(DecimalEncoder, self).default(o)

app = FastAPI(title="MCP SQL Server (SSE)", version="1.0")
security = HTTPBearer(auto_error=False)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

API_KEY = os.getenv("MCP_API_KEY")

def verify_token(request: Request):
    """手动验证 Bearer Token（因 SSE 不支持 Depends）"""
    if not API_KEY:
        return True
    auth = request.headers.get("authorization", "")
    if auth.startswith("Bearer ") and auth[7:] == API_KEY:
        return True
    raise HTTPException(status_code=403, detail="Invalid or missing API key")

# ======================
# /manifest - Dify 用于发现工具
# ======================
@app.get("/manifest")
async def get_manifest():
    return {
        "name": "sql_database_query",
        "description": "Securely query PostgreSQL/MySQL via natural language.",
        "version": "1.0.0",
        "tools": [
            {
                "name": "query_database",
                "description": "Execute a SELECT SQL query on allowed tables.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "sql": {"type": "string", "description": "Valid SELECT SQL"}
                    },
                    "required": ["sql"]
                }
            }
        ]
    }

# ======================
# 工具执行逻辑（复用）
# ======================
def execute_safe_query(sql: str) -> dict:
    sql = sql.strip()
    if not sql:
        raise ValueError("SQL is empty")
    
    sql_lower = sql.lower()
    if not sql_lower.startswith("select"):
        raise ValueError("Only SELECT allowed")
    
    for kw in FORBIDDEN_KEYWORDS:
        if kw in sql_lower:
            raise ValueError(f"Forbidden keyword: {kw}")
    
    from_match = re.search(r'\bfrom\s+([a-zA-Z_][a-zA-Z0-9_]*)', sql_lower)
    if from_match:
        table = from_match.group(1)
        if table not in ALLOWED_TABLES:
            raise ValueError(f"Table '{table}' not allowed")
    
    # 执行查询
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
    
    try:
        with conn.cursor() as cur:
            cur.execute(sql)
            columns = [desc[0] for desc in cur.description]
            rows = [dict(zip(columns, row)) for row in cur.fetchall()]
        return {"data": rows, "count": len(rows)}
    finally:
        conn.close()

# ======================
# /sse - 标准 MCP over SSE 端点
# ======================
@app.get("/sse")
async def mcp_sse(request: Request):
    verify_token(request)
    
    async def event_generator():
        # 读取请求体（SSE 连接建立后，客户端会发送一个 JSON 行）
        body = await request.body()
        if not body:
            yield {"event": "error", "data": json.dumps({"message": "Empty request"})}
            return

        try:
            payload = json.loads(body.decode("utf-8"))
            logger.info(f"[MCP SSE] Received: {payload}")

            # 必须是 call 类型
            if payload.get("type") != "call":
                yield {"event": "error", "data": json.dumps({"message": "Only 'call' type supported"})}
                return

            tool_name = payload.get("tool")
            args = payload.get("arguments", {})
            call_id = payload.get("call_id")

            if tool_name != "query_database":
                yield {"event": "error", "data": json.dumps({"message": f"Tool '{tool_name}' not found"})}
                return

            sql = args.get("sql")
            if not isinstance(sql, str):
                raise ValueError("Missing 'sql' string argument")

            # 执行查询
            result = execute_safe_query(sql)

            # 返回 result 事件
            yield {
                "event": "result",
                "data": json.dumps({
                    "call_id": call_id,
                    "result": result
                }, cls=DecimalEncoder)
            }

        except Exception as e:
            logger.error(f"SSE error: {e}")
            yield {
                "event": "error",
                "data": json.dumps({
                    "call_id": payload.get("call_id"),
                    "message": str(e)
                }, cls=DecimalEncoder)
            }

        finally:
            # 可选：发送 done（非必须，连接可保持）
            yield {"event": "done", "data": ""}

    return EventSourceResponse(event_generator(), media_type="text/event-stream")

# ======================
# 健康检查
# ======================
@app.get("/health")
def health():
    return {"status": "ok", "mode": "sse"}
