# ai_ma · Dockerfile (macOS 本地部署)
# 单镜像: Python + Django + ai_ma_zlm (ZLMediaKit 定制版)
# 注意: gcc9.4 构建的 .so 需要较新的 glibc; debian:bookworm (glibc 2.36) 前向兼容
FROM debian:bookworm-slim AS base

WORKDIR /app

# 系统依赖 (libc6/glibc 由基础镜像提供; ca-certificates 供 pip/curl 用)
RUN apt-get update && apt-get install -y --no-install-recommends \
        libc6 ca-certificates curl python3-dev gcc ca-certificates \
        libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*
# 安装 Python 3 (bookworm 自带 python3.11)
RUN apt-get update && apt-get install -y --no-install-recommends \
        python3 python3-pip ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# python3 -> python 软链 (Django/manage.py 调用 python3; 部分依赖可能用 python)
RUN ln -sf $(which python3) /usr/local/bin/python || true
RUN ln -sf $(which pip3) /usr/local/bin/pip || true

WORKDIR /app

# 安装 Python 依赖 (CPU-only torch: 无 GPU, 跳过 CUDA 包, 大幅减小体积)
# 使用阿里云 PyPI 镜像加速（官方源直连仅 ~30KB/s）
# torch 使用上海交大 pytorch-wheels 镜像（清华镜像已下线; 需保证 torch>=2.10 含 2.14.0+cpu）
COPY requirements-linux.txt ./
RUN pip3 install --no-cache-dir --break-system-packages \
        -i https://mirrors.aliyun.com/pypi/simple/ \
        --extra-index-url https://mirror.sjtu.edu.cn/pytorch-wheels/cpu \
        -r requirements-linux.txt

# 拷贝项目源码
COPY . .

# 让 ai_ma_zlm 可执行 (git checkout 可能丢失 +x)
RUN chmod +x zlm/bin.x86.gcc9.4/ai_ma_zlm || true

# 创建可写工作目录 (ZLM 运行时需要)
RUN mkdir -p /app/www /app/record /app/ffmpeg /app/logs

WORKDIR /app

# 容器内端口: 8001 (web), 10001 (Django admin hook), 10002 (ZLM API)
EXPOSE 8001 10001 10002

# ZLM 运行环境 (捆绑 .so 需 LD_LIBRARY_PATH)
ENV LD_LIBRARY_PATH=/app/zlm/bin.x86.gcc9.4:${LD_LIBRARY_PATH} \
    PYTHONUNBUFFERED=1 \
    ZLM_BIN=/app/zlm/bin.x86.gcc9.4/ai_ma_zlm \
    ZLM_CONFIG=/app/zlm/bin.x86.gcc9.4/config.ini

# 自定义启动脚本 (先启 ZLM, 再启 Django)
COPY start.sh /app/start.sh
RUN chmod +x /app/start.sh

CMD ["/app/start.sh"]
