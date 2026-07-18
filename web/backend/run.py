"""本地开发入口：8001 + 热重载，对齐 web/frontend/vite.config.ts 的 proxy。

生产/容器不用这个文件——Dockerfile CMD 直接 uvicorn 绑 8000（nginx 代理目标）。
"""
import uvicorn

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="127.0.0.1", port=8001, reload=True)
