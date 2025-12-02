import re
import logging
import os
from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.security import HTTPBearer
from pydantic import BaseModel
from typing import Any, Dict, List
import psycopg2
import pymysql

from config import DATABASE_URL, DB_TYPE, ALLOWED_TABLES, ALLOWED_COLUMNS, FORBIDDEN_KEYWORDS

app = FastAPI(title="MCP SQL Server", version="1.0")
security = HTTPBearer(auto_error=False)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Optional: API Key from env
API_KEY = os.getenv("MCP_API_KEY")

def verify_token(credentials = Depends(security)):
    if API_KEY and (not credentials or credentials.credentials != API_KEY):
        raise HTTPException(status_code=403, detail="Invalid or missing API key")

class MCPRequest(BaseModel):
    method: str
    params: Dict[str, Any]

def validate_sql(sql: str) -> None:
    sql_lower = sql.lower().strip()
    if not sql_lower.startswith("select"):
        raise HTTPException(status_code=400, detail="Only SELECT queries allowed")
    
    for kw in FORBIDDEN_KEYWORDS:
        if kw in sql_lower:
            raise HTTPException(status_code=400, detail=f"Forbidden keyword: {kw}")
    
    # Extract table after FROM
    from_match = re.search(r'\bfrom\s+([a-zA-Z_][a-zA-Z0-9_]*)', sql_lower)
    if from_match:
        table = from_match.group(1)
        if table not in ALLOWED_TABLES:
            raise HTTPException(status_code=400, detail=f"Table '{table}' not allowed")

def execute_query(sql: str) -> List[Dict[str, Any]]:
    validate_sql(sql)
    
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
        raise ValueError(f"Unsupported DB_TYPE: {DB_TYPE}")
    
    try:
        with conn.cursor() as cur:
            cur.execute(sql)
            columns = [desc[0] for desc in cur.description]
            rows = [dict(zip(columns, row)) for row in cur.fetchall()]
        return rows
    finally:
        conn.close()

@app.post("/mcp", dependencies=[Depends(verify_token) if API_KEY else Depends(lambda: None)])
async def mcp_endpoint(request: MCPRequest, req: Request):
    client_ip = req.client.host
    logger.info(f"[MCP] {client_ip} → method={request.method}")
    
    if request.method != "query_database":
        raise HTTPException(status_code=400, detail="Unsupported method")
    
    sql = request.params.get("sql")
    if not isinstance(sql, str) or not sql.strip():
        raise HTTPException(status_code=400, detail="Missing valid 'sql' parameter")
    
    try:
        result = execute_query(sql)
        return {"result": {"data": result, "count": len(result), "success": True}}
    except Exception as e:
        logger.error(f"Query failed: {e}")
        raise HTTPException(status_code=500, detail=f"Execution error: {str(e)}")

@app.get("/health")
def health():
    return {"status": "ok", "db_type": DB_TYPE}
