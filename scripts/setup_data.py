"""Set up local datasets for the data-gated single-cell MCP servers.

Usage:
    python scripts/setup_data.py --list                 # show datasets + local status
    python scripts/setup_data.py --dataset depmap        # fetch one (if a stable URL exists)
    python scripts/setup_data.py --all                   # fetch everything with a stable URL
    python scripts/setup_data.py --check                 # verify presence + checksums

Datasets without a stable direct URL (most single-cell atlases live behind portals or
release-specific links) print manual download instructions instead of failing. Downloads are
idempotent: an existing, correctly-sized/checksummed file is skipped.
"""
from __future__ import annotations

import argparse
import hashlib
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from datasets import DATASETS, Dataset  # noqa: E402

DATA_DIR = Path(os.getenv("VB_DATA_DIR", Path(__file__).resolve().parents[1] / "data"))


def dest_path(d: Dataset) -> Path:
    return DATA_DIR / d.dest


def is_present(d: Dataset) -> bool:
    return d.dest != "(none — API)" and dest_path(d).exists()


def sha256_of(path: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while block := f.read(chunk):
            h.update(block)
    return h.hexdigest()


def _download(url: str, dest: Path) -> None:
    import httpx

    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    print(f"  downloading {url}")
    with httpx.stream("GET", url, follow_redirects=True, timeout=None) as r:
        r.raise_for_status()
        total = int(r.headers.get("content-length", 0))
        done = 0
        with tmp.open("wb") as f:
            for chunk in r.iter_bytes(1 << 20):
                f.write(chunk)
                done += len(chunk)
                if total:
                    pct = 100 * done / total
                    print(f"\r  {done/1e6:.0f}/{total/1e6:.0f} MB ({pct:.0f}%)", end="", flush=True)
        print()
    tmp.replace(dest)


def fetch(d: Dataset, use_sample: bool = False) -> None:
    if is_present(d):
        print(f"[skip] {d.key}: already present at {dest_path(d)}")
        return
    url = d.sample_url if (use_sample and d.sample_url) else d.url
    if not url:
        print(f"[manual] {d.key}: {d.description}")
        print(f"         dest: {dest_path(d)}")
        print(f"         {d.manual}")
        return
    _download(url, dest_path(d))
    if d.sha256:
        got = sha256_of(dest_path(d))
        status = "ok" if got == d.sha256 else f"MISMATCH (got {got[:12]}…)"
        print(f"  checksum: {status}")
    print(f"[done] {d.key} -> {dest_path(d)}")


def cmd_list() -> None:
    print(f"VB_DATA_DIR = {DATA_DIR}\n")
    for d in DATASETS.values():
        mark = "present" if is_present(d) else ("API" if d.dest == "(none — API)" else "missing")
        src = "direct-url" if d.url else "manual"
        print(f"  {d.key:16s} [{mark:8s}] ({src}, {d.approx_size})  server={d.server}")
        print(f"      {d.description}")


def cmd_check() -> int:
    problems = 0
    for d in DATASETS.values():
        if d.dest == "(none — API)":
            continue
        if not is_present(d):
            print(f"[missing] {d.key}: expected {dest_path(d)}")
            problems += 1
            continue
        if d.sha256:
            got = sha256_of(dest_path(d))
            if got != d.sha256:
                print(f"[checksum] {d.key}: MISMATCH")
                problems += 1
                continue
        print(f"[ok] {d.key}")
    return problems


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--list", action="store_true", help="list datasets + status")
    p.add_argument("--check", action="store_true", help="verify presence/checksums")
    p.add_argument("--dataset", help="fetch a single dataset by key")
    p.add_argument("--all", action="store_true", help="fetch all datasets with a stable URL")
    p.add_argument("--sample", action="store_true", help="prefer smaller sample subsets where available")
    args = p.parse_args(argv)

    if args.list or not (args.check or args.dataset or args.all):
        cmd_list()
        return 0
    if args.check:
        return 0 if cmd_check() == 0 else 1
    if args.dataset:
        if args.dataset not in DATASETS:
            print(f"unknown dataset '{args.dataset}'. Known: {', '.join(DATASETS)}")
            return 2
        fetch(DATASETS[args.dataset], use_sample=args.sample)
        return 0
    if args.all:
        for d in DATASETS.values():
            fetch(d, use_sample=args.sample)
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
