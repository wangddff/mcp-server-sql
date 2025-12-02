# MCP Server for SQL Databases (PostgreSQL / MySQL)

A secure, production-ready MCP (Model Context Protocol) server that allows LLMs (via Dify, Cursor, etc.) to query traditional databases with natural language.

## ✨ Features
- Supports PostgreSQL and MySQL
- SQL injection prevention
- Table/column allowlist
- Forbidden keyword blocking
- Docker ready
- Compatible with Dify Custom Tool

## 🚀 Quick Start

```bash
# Build
docker build -t mcp-server-sql .

# Run (PostgreSQL example)
docker run -d \
  --name mcp-sql \
  -p 8000:8000 \
  -e DATABASE_URL="postgresql://user:pass@host:5432/db" \
  -e DB_TYPE="postgresql" \
  mcp-server-sql
