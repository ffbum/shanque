"""Shanque shared server entry point."""
import argparse
from pathlib import Path
from waitress import create_server
from workspace import create_app

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="山雀企业项目工作台 · 多人服务")
    parser.add_argument("--server", action="store_true", help="兼容参数，默认即多人服务模式")
    parser.add_argument("--port", type=int, default=5086)
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--data-dir", type=Path, default=Path(__file__).resolve().parent / "instance" / "server")
    args = parser.parse_args()
    if not (Path(__file__).resolve().parent / "frontend/dist/index.html").is_file():
        parser.error("请先执行 npm run frontend:build 构建前端。")
    app = create_app({"SERVER_MODE": True, "SESSION_COOKIE_NAME": "shanque_session"}, instance_path=str(args.data_dir.resolve()))
    server = create_server(app, host=args.host, port=args.port, threads=8)
    print(f"山雀企业项目工作台已启动，监听 {args.host}:{server.effective_port}。请通过服务器地址访问。", flush=True)
    server.run()
