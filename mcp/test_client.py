import asyncio
# 1. 引入 ClientSession
from mcp import ClientSession
from mcp.client.sse import sse_client

async def run_test():
    # 替换为你的服务器地址
    url = "http://localhost:8000/sse"
    
    print(f"🔌 Connecting to {url}...")
    
    # sse_client 返回的是底层流 (read_stream, write_stream)
    async with sse_client(url) as streams:
        # 2. 关键修改：将流传入 ClientSession
        async with ClientSession(streams[0], streams[1]) as session:
            print("✅ SSE Connected!")
            
            # 3. 现在可以在 session 上调用 initialize 了
            print("🤝 Initializing handshake...")
            await session.initialize()
            print("✅ Handshake complete!")
            
            # 4. 列出可用工具
            print("\n🔍 Listing tools...")
            tools = await session.list_tools()
            print(f"Found {len(tools.tools)} tools:")
            for tool in tools.tools:
                print(f" - {tool.name}: {tool.description}")

            # 5. 调用工具 (测试 SQL)
            print("\n🚀 Calling tool 'query_database'...")
            try:
                # 注意：确保你的数据库里真的有数据，或者改用 select 1
                result = await session.call_tool(
                    name="query_database",
                    arguments={"sql": "SELECT 1 as test_val"}
                )
                print("✅ Result received:")
                # 解析并打印结果
                print(result.content[0].text)
            except Exception as e:
                print(f"❌ Tool call failed: {e}")

if __name__ == "__main__":
    asyncio.run(run_test())
