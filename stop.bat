@echo off
chcp 65001 >nul
echo ============================================
echo  停止 GEO 监测系统全部服务
echo ============================================

echo [1/3] 停止后台数据库进程 (PostgreSQL / Redis)...
taskkill /F /IM postgres.exe >nul 2>&1
taskkill /F /IM redis-server.exe >nul 2>&1

echo [2/3] 停止端口占用进程 (8000=FastAPI, 5173=Vue)...
for /f "tokens=5" %%p in ('netstat -aon ^| findstr ":8000 " ^| findstr "LISTENING"') do taskkill /F /PID %%p >nul 2>&1
for /f "tokens=5" %%p in ('netstat -aon ^| findstr ":5173 " ^| findstr "LISTENING"') do taskkill /F /PID %%p >nul 2>&1

echo [3/3] 完成。
echo  - FastAPI / Vue 已停止（端口已释放）
echo  - Celery 窗口请手动关闭（无固定端口，脚本无法识别）
pause
