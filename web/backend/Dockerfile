FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/
COPY run.py .

RUN mkdir -p /app/data

EXPOSE 8000

# 容器内不用 run.py（那是本地开发入口：8001 + reload，对齐 vite proxy）。
# 这里必须绑 8000——frontend/nginx.conf 的 proxy_pass 指向 backend:8000。
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
