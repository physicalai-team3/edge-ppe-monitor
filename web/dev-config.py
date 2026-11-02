"""Docker 없이 대시보드 띄우기: 루트 .env → web/public/config.js (40-write-config.sh 와 같은 내용).

    python web/dev-config.py            # config.js 만 만든다
    python web/dev-config.py --serve    # 만들고 http://localhost:8080 으로 띄운다 (WEB_PORT)

브라우저에 노출해도 되는 값만 넣는다 (secret 키 금지).
"""
import argparse
import functools
import http.server
import json
import os
from pathlib import Path

WEB = Path(__file__).resolve().parent
PUBLIC = WEB / "public"
KEYS = ("SUPABASE_URL", "SUPABASE_PUBLISHABLE_KEY", "SUPABASE_BUCKET")


def read_env(path: Path) -> dict:
    values = {}
    if path.is_file():
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                values[key.strip()] = value.strip()
    values.update({k: v for k, v in os.environ.items() if k in KEYS + ("WEB_PORT",)})
    return values


def write_config(env: dict) -> None:
    config = {
        "SUPABASE_URL": env.get("SUPABASE_URL", ""),
        "SUPABASE_PUBLISHABLE_KEY": env.get("SUPABASE_PUBLISHABLE_KEY", ""),
        "SUPABASE_BUCKET": env.get("SUPABASE_BUCKET") or "violation-images",
    }
    (PUBLIC / "config.js").write_text(
        f"window.PPE_CONFIG = {json.dumps(config, indent=2)};\n", encoding="utf-8")
    print(f"[web] config.js written (url={config['SUPABASE_URL'] or '(비어 있음)'})")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--serve", action="store_true", help="web/public 을 정적 서버로 띄운다")
    args = parser.parse_args()
    env = read_env(WEB.parent / ".env")
    write_config(env)
    if args.serve:
        port = int(env.get("WEB_PORT") or 8080)
        handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(PUBLIC))
        print(f"[web] http://localhost:{port}  (Ctrl+C 로 멈춤)")
        http.server.ThreadingHTTPServer(("127.0.0.1", port), handler).serve_forever()


if __name__ == "__main__":
    main()
