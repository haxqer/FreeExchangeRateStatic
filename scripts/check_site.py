#!/usr/bin/env python3
"""Skip duplicate Pages deployments while recovering unsuccessful deployments."""

import argparse
from http.client import HTTPException
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def needs_deployment(site_url: str, files: tuple[Path, ...], site_root: Path | None = None) -> bool:
    for file in files:
        expected = file.read_bytes()
        public_path = file.relative_to(site_root).as_posix() if site_root is not None else file.name
        request = Request(
            f"{site_url.rstrip('/')}/{public_path}",
            headers={"Cache-Control": "no-cache"},
        )
        try:
            with urlopen(request, timeout=10) as response:
                if response.read(len(expected) + 1) != expected:
                    return True
        except (URLError, OSError, HTTPException, ValueError) as error:
            # A missing or unreachable site must not prevent a deployment retry.
            if isinstance(error, HTTPError):
                error.close()
            return True
    return False


def public_files(site_root: Path) -> tuple[Path, ...]:
    files = (site_root / "latest.json", site_root / "index.html")
    if (site_root / "history").exists():
        # Daily index hashes in the root index cover all immutable hourly files.
        files += (site_root / "history/index.json",)
    return files


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--site-url", required=True)
    parser.add_argument("--site-root", type=Path, default=Path("."))
    args = parser.parse_args()
    deploy = needs_deployment(args.site_url, public_files(args.site_root), args.site_root)
    print(f"deploy={str(deploy).lower()}")


if __name__ == "__main__":
    main()
