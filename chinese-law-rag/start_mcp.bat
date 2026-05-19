@echo off
cd /d E:\Hanko-workspace\law_data
echo === 中国法律 MCP Server ===
echo 启动中...
start /B python mcp_server_local.py > mcp_local.log 2>&1
echo 服务已启动: http://localhost:8765/sse
echo 日志文件: mcp_local.log
echo 关闭此窗口不会停止服务。停止请运行 stop.bat
pause
