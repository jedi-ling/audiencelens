FROM python:3.11-slim

# 容器内的目录结构必须**镜像仓库结构**（<repo>/web/backend），不能把 app/ 平铺到 /app。
#
# 原因：后端多处用「从本文件往上数几级」定位仓库资源——
#   config.py:124    repo_root    = dirname(dirname(backend_dir))   -> src/ 与 src/personas/
#   ethics_service   PROJECT_ROOT = 从 app/services 往上四级        -> audiencelens-v0.2-harness/
#   config.py:45     env_path     = parents[2] / ".env"             -> web/.env
# 这些推算在宿主机上成立，因为文件真的在 <repo>/web/backend/app/ 下。
# 曾经 WORKDIR=/app + COPY app/ ./app/ 让 app/ 落在 /app/app/，于是
# backend_dir=/app、repo_root=dirname(dirname("/app"))="/"，代码去 /src 找引擎，
# 而 compose 把 src 挂在 /app/src —— `from runner...` 必然 ModuleNotFoundError，
# 容器根本起不来。逐个改挂载只能治一处，对齐层级才是一次修完所有路径。
WORKDIR /app/web/backend

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/
COPY run.py .

# 与 config.py 的 default_db（backend_dir/data/reviews.db）一致；compose 挂同一路径
RUN mkdir -p /app/web/backend/data

EXPOSE 8000

# 容器内不用 run.py（那是本地开发入口：8001 + reload，对齐 vite proxy）。
# 这里必须绑 8000——frontend/nginx.conf 的 proxy_pass 指向 backend:8000。
# --proxy-headers + --forwarded-allow-ips 不是可选项：限流按 request.client.host
# 分桶（deps._client_key），而经 nginx 反代后所有请求的 peer IP 都是同一个容器 IP。
# 少了这两个参数，"每 IP 10 次注册/小时"就变成**全站每小时 10 次**——任意一人
# 注册 10 次即可让全站一小时内无法注册、且因为 register 与 login 共用限流桶，
# 连登录一起封死。裸机手册（DEPLOY-BAREMETAL.md）一直是配了的，容器这条漏了，
# 两种部署形态在这一点上行为不一致，而容器是主推的那条。
#
# forwarded-allow-ips 用 * 而不是具体 IP：compose 网络里 nginx 容器的地址是
# 动态分配的，写死会在重建网络后失效（失效表现为静默回退到 peer IP，
# 也就是悄悄退回上面那个全站共用桶的状态）。容器只接受来自 compose 网络的
# 连接、不直接暴露公网端口，这个放宽是安全的——反之若把 8000 直接暴露出去，
# 任何人都能伪造 X-Forwarded-For 绕过限流，所以 compose 里绝不要给它加端口映射。
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", \
     "--proxy-headers", "--forwarded-allow-ips", "*"]
