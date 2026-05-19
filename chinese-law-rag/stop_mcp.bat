@echo off
taskkill /FI "WINDOWTITLE eq mcp_server_local*" /F 2>nul
taskkill /FI "IMAGENAME eq python.exe" /FI "MEMUSAGE gt 50000" /F 2>nul
echo MCP Server 已停止
pause
