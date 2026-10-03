#!/usr/bin/env python3
"""Skip duplicate Pages deployments while recovering unsuccessful deployments."""

import argparse
from http.client import HTTPException
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def needs_deployment(site_url: str, files: tuple[Path, ...]) -> bool:
    for file in files:
        expected = file.read_bytes()
        request = Request(
            f"{site_url.rstrip('/')}/{file.name}",
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


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--site-url", required=True)
    args = parser.parse_args()
    deploy = needs_deployment(args.site_url, (Path("latest.json"), Path("index.html")))
    print(f"deploy={str(deploy).lower()}")


if __name__ == "__main__":
    main()
