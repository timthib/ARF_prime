"""Start the control room.

    python3 -m monitor
    python3 -m monitor --root runs/control-room --port 8501
"""

from __future__ import annotations

import argparse
from pathlib import Path

from monitor.fixture import build_demo
from monitor.queries import repo_root
from monitor.server import make_server


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="ARF control room (D1 only)")
    parser.add_argument("--root", default="runs/control-room", help="directory of run logs")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8501)
    args = parser.parse_args(argv)
    root = Path(args.root)
    if not (root / "index.json").exists():
        build_demo(root)
        print(f"wrote a synthetic demo under {root}")
    server = make_server(args.host, args.port, root, repo_root())
    print(f"control room at http://{args.host}:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
