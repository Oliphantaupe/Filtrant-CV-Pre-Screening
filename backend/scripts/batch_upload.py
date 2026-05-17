#!/usr/bin/env python3
"""
Batch upload CVs to the Filtrant backend.

Usage:
    python backend/scripts/batch_upload.py ./path/to/cvs/
    python backend/scripts/batch_upload.py ./path/to/cvs/ --backend https://your-backend.up.railway.app
    python backend/scripts/batch_upload.py ./path/to/cvs/ --concurrency 10
"""
import argparse
import asyncio
import pathlib
import sys

try:
    import httpx
except ImportError:
    sys.exit("httpx is required: pip install httpx")

DEFAULT_BACKEND = "https://filtrant-cv-pre-screening-production.up.railway.app"
SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".doc"}


async def upload(client: httpx.AsyncClient, path: pathlib.Path, backend: str) -> dict:
    with open(path, "rb") as f:
        data = f.read()
    try:
        r = await client.post(
            f"{backend}/api/v1/upload",
            files={"file": (path.name, data)},
            timeout=120,
        )
        if r.status_code == 201:
            result = r.json()
            return {"file": path.name, "status": "ok", **result}
        elif r.status_code == 409:
            return {"file": path.name, "status": "duplicate"}
        else:
            return {"file": path.name, "status": "error", "detail": r.text}
    except Exception as e:
        return {"file": path.name, "status": "error", "detail": str(e)}


def print_result(result: dict) -> None:
    status = result["status"]
    name = result["file"]
    if status == "ok":
        rec = result.get("recommendation", "?")
        conf = result.get("confidence")
        conf_str = f" ({conf:.0%})" if conf is not None else ""
        print(f"  ✓  {name:<40} → {rec}{conf_str}")
    elif status == "duplicate":
        print(f"  ~  {name:<40} → already processed")
    else:
        print(f"  ✗  {name:<40} → {result.get('detail', 'unknown error')}")


async def main(cv_dir: pathlib.Path, backend: str, concurrency: int) -> None:
    files = [p for p in cv_dir.iterdir() if p.suffix.lower() in SUPPORTED_EXTENSIONS]
    if not files:
        sys.exit(f"No PDF/DOCX files found in {cv_dir}")

    print(f"Uploading {len(files)} CV(s) to {backend} (concurrency={concurrency})\n")

    sem = asyncio.Semaphore(concurrency)
    results = {"ok": 0, "duplicate": 0, "error": 0}

    async with httpx.AsyncClient() as client:
        async def guarded(p: pathlib.Path):
            async with sem:
                result = await upload(client, p, backend)
                print_result(result)
                results[result["status"]] = results.get(result["status"], 0) + 1

        await asyncio.gather(*[guarded(p) for p in sorted(files)])

    print(f"\n{results['ok']} succeeded · {results['duplicate']} duplicates · {results['error']} errors")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Batch upload CVs to Filtrant")
    parser.add_argument("directory", type=pathlib.Path, help="Folder containing CV files")
    parser.add_argument("--backend", default=DEFAULT_BACKEND, help="Backend base URL")
    parser.add_argument("--concurrency", type=int, default=5, help="Parallel uploads (default: 5)")
    args = parser.parse_args()

    if not args.directory.is_dir():
        sys.exit(f"Not a directory: {args.directory}")

    asyncio.run(main(args.directory, args.backend.rstrip("/"), args.concurrency))
