"""Start the hold-out room on 127.0.0.1 only.

    python3 -m d0vault
"""

from __future__ import annotations

import argparse
from pathlib import Path

from d0vault.fixture import build_demo
from d0vault.server import make_server


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="ARF D0 room (one user, loopback)")
    parser.add_argument("--root", default="runs/d0-room")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8502)
    args = parser.parse_args(argv)
    root = Path(args.root)
    if not (root / "d0_results.sqlite").exists():
        password = build_demo(root)
        print(f"synthetic vault written under {root}")
        print(f"D0 password, shown once: {password}")
        print("It is not stored in the tree. Keep it; L0 and L1 must not see it.")
    server = make_server(args.host, args.port, root)
    print(f"D0 room at http://127.0.0.1:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
