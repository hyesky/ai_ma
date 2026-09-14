#!/bin/bash
# ai_ma · 启动脚本
# 先启动 ZLM (ai_ma_zlm), 再启动 Django
set -e

echo "[start] 初始化工作目录..."
mkdir -p /app/www /app/record /app/ffmpeg /app/logs

# ZLM 运行需要捆绑 .so
export LD_LIBRARY_PATH="/app/zlm/bin.x86.gcc9.4:${LD_LIBRARY_PATH}"

echo "[start] 启动 ZLMediaKit (ai_ma_zlm)..."
"$ZLM_BIN" -c "$ZLM_CONFIG" &
ZLM_PID=$!
echo "[start] ZLM PID=$ZLM_PID, 等待 API 就绪..."
sleep 3

# 检查 ZLM API
if curl -s -o /dev/null -X POST "http://127.0.0.1:10002/index/api/getThreadsLoad?secret=$(grep '^secret' "$ZLM_CONFIG" | cut -d= -f2)" -H "User-Agent: ai_ma" -d '{}'; then
    echo "[start] ZLM API 正常"
else
    echo "[start] WARNING: ZLM API 未响应 (可能仍在启动)"
fi

echo "[start] 启动 Django..."
exec python3 manage.py runserver 0.0.0.0:10001
