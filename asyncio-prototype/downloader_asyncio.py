#!/usr/bin/env python3
"""Asyncio prototype: concurrent file downloader with retries and reporting.

This is intentionally structured for learning rather than minimal code size.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Optional

import aiofiles
import aiohttp


CHUNK_SIZE = 64 * 1024
PROJECT_DIR = Path(__file__).resolve().parent


class FileStatus(str, Enum):
    QUEUED = "queued"
    DOWNLOADING = "downloading"
    COMPLETED = "completed"
    FAILED = "failed"


class DownloadError(Exception):
    """Base download error for classification."""


class TransientDownloadError(DownloadError):
    """Error type that may succeed on retry."""


class PermanentDownloadError(DownloadError):
    """Error type that should not be retried."""


@dataclass
class DownloadSpec:
    url: str
    output: str
    sha256: Optional[str] = None


@dataclass
class DownloadResult:
    url: str
    output: str
    expected_sha256: Optional[str] = None
    status: FileStatus = FileStatus.QUEUED
    attempts: int = 0
    bytes_downloaded: int = 0
    http_status: Optional[int] = None
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    duration_seconds: Optional[float] = None
    error: Optional[str] = None
    checksum_verified: Optional[bool] = None
    computed_sha256: Optional[str] = None
    last_updated: str = field(default_factory=lambda: utc_now_iso())


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def resolve_project_path(raw_path: str) -> Path:
    candidate = Path(raw_path).expanduser()
    if candidate.is_absolute():
        return candidate
    return PROJECT_DIR / candidate


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Asyncio concurrent file downloader prototype")
    parser.add_argument(
        "manifest",
        help=(
            "Path to JSON file containing [{'url': ..., 'output': ..., 'sha256': optional}]. "
            "Relative paths resolve from this script's folder."
        ),
    )
    parser.add_argument(
        "--report",
        default="download_report.json",
        help="Path for final JSON report (default: download_report.json)",
    )
    parser.add_argument(
        "--max-concurrency",
        type=int,
        default=5,
        help="Maximum simultaneous in-flight downloads (default: 5)",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=8,
        help="Number of worker tasks pulling from queue (default: 8)",
    )
    parser.add_argument(
        "--retries",
        type=int,
        default=3,
        help="Retries for transient failures (default: 3)",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=30.0,
        help="Request timeout in seconds (default: 30)",
    )
    return parser.parse_args()


async def load_manifest(path: str) -> list[DownloadSpec]:
    manifest_path = resolve_project_path(path)
    async with aiofiles.open(manifest_path, "r", encoding="utf-8") as f:
        raw = await f.read()

    data = json.loads(raw)
    if not isinstance(data, list):
        raise ValueError("Manifest must be a list of download entries")

    specs: list[DownloadSpec] = []
    for idx, item in enumerate(data):
        if not isinstance(item, dict):
            raise ValueError(f"Manifest entry {idx} must be an object")
        url = item.get("url")
        output = item.get("output")
        sha256 = item.get("sha256")
        if not isinstance(url, str) or not isinstance(output, str):
            raise ValueError(f"Manifest entry {idx} requires string fields: 'url' and 'output'")
        if sha256 is not None and not isinstance(sha256, str):
            raise ValueError(f"Manifest entry {idx} has non-string 'sha256'")
        specs.append(DownloadSpec(url=url, output=output, sha256=sha256))

    return specs


def set_status(result: DownloadResult, status: FileStatus) -> None:
    result.status = status
    result.last_updated = utc_now_iso()
    print(f"[{result.last_updated}] {result.output}: {status.value}")


async def write_report(path: str, results: list[DownloadResult]) -> None:
    payload = {
        "generated_at": utc_now_iso(),
        "total_files": len(results),
        "completed": sum(1 for r in results if r.status == FileStatus.COMPLETED),
        "failed": sum(1 for r in results if r.status == FileStatus.FAILED),
        "results": [serialize_result(r) for r in results],
    }

    async with aiofiles.open(path, "w", encoding="utf-8") as f:
        await f.write(json.dumps(payload, indent=2, sort_keys=False))


def serialize_result(result: DownloadResult) -> dict[str, Any]:
    raw = asdict(result)
    raw["status"] = result.status.value
    return raw


async def remove_file_if_exists(path: Path) -> None:
    if path.exists():
        await asyncio.to_thread(path.unlink)


async def compute_sha256(path: Path) -> str:
    import hashlib

    digest = hashlib.sha256()
    async with aiofiles.open(path, "rb") as f:
        while True:
            chunk = await f.read(CHUNK_SIZE)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


async def download_once(
    session: aiohttp.ClientSession,
    spec: DownloadSpec,
    result: DownloadResult,
    semaphore: asyncio.Semaphore,
) -> None:
    target_path = resolve_project_path(spec.output)
    temp_path = target_path.with_suffix(target_path.suffix + ".part")
    target_path.parent.mkdir(parents=True, exist_ok=True)

    # Tradeoff: using a temp file avoids partially-written final outputs,
    # but creates an extra rename step and small amount of disk churn.
    await remove_file_if_exists(temp_path)

    async with semaphore:
        async with session.get(spec.url) as response:
            result.http_status = response.status

            if response.status >= 500 or response.status in {408, 429}:
                raise TransientDownloadError(f"HTTP {response.status}")
            if response.status >= 400:
                raise PermanentDownloadError(f"HTTP {response.status}")

            bytes_downloaded = 0
            async with aiofiles.open(temp_path, "wb") as out:
                async for chunk in response.content.iter_chunked(CHUNK_SIZE):
                    # Streaming keeps memory bounded even for large files.
                    await out.write(chunk)
                    bytes_downloaded += len(chunk)

            result.bytes_downloaded = bytes_downloaded

    await asyncio.to_thread(os.replace, temp_path, target_path)


async def verify_checksum_if_needed(spec: DownloadSpec, result: DownloadResult) -> None:
    if not spec.sha256:
        result.checksum_verified = None
        result.computed_sha256 = None
        return

    target_path = resolve_project_path(spec.output)
    computed = await compute_sha256(target_path)
    result.computed_sha256 = computed
    result.checksum_verified = computed.lower() == spec.sha256.lower()
    if not result.checksum_verified:
        # Keep failed verification outcomes explicit by removing bad artifacts.
        await remove_file_if_exists(target_path)
        raise PermanentDownloadError(
            f"SHA256 mismatch: expected={spec.sha256.lower()} got={computed.lower()}"
        )


def is_transient_exception(exc: Exception) -> bool:
    if isinstance(exc, (TransientDownloadError, asyncio.TimeoutError)):
        return True
    if isinstance(exc, aiohttp.ClientConnectionError):
        return True
    if isinstance(exc, aiohttp.ClientPayloadError):
        return True
    if isinstance(exc, aiohttp.ServerDisconnectedError):
        return True
    return False


async def process_spec(
    session: aiohttp.ClientSession,
    spec: DownloadSpec,
    result: DownloadResult,
    semaphore: asyncio.Semaphore,
    max_retries: int,
) -> None:
    first_start = datetime.now(timezone.utc)
    result.started_at = first_start.isoformat()

    try:
        for attempt in range(1, max_retries + 2):
            result.attempts = attempt
            set_status(result, FileStatus.DOWNLOADING)

            try:
                await download_once(session, spec, result, semaphore)
                await verify_checksum_if_needed(spec, result)
                result.error = None
                set_status(result, FileStatus.COMPLETED)
                return
            except Exception as exc:
                # Ensure failed attempt does not leave partial artifacts.
                target_path = resolve_project_path(spec.output)
                await remove_file_if_exists(target_path.with_suffix(target_path.suffix + ".part"))

                if is_transient_exception(exc) and attempt <= max_retries:
                    # Tradeoff: simple linear backoff keeps logic readable.
                    # Exponential backoff is better at scale but noisier for a prototype.
                    delay_seconds = float(attempt)
                    result.error = f"Retrying after transient error: {exc}"
                    set_status(result, FileStatus.QUEUED)
                    await asyncio.sleep(delay_seconds)
                    continue

                result.error = str(exc)
                set_status(result, FileStatus.FAILED)
                return
    finally:
        finished = datetime.now(timezone.utc)
        result.finished_at = finished.isoformat()
        result.duration_seconds = (finished - first_start).total_seconds()


async def worker_loop(
    name: str,
    queue: asyncio.Queue[Optional[DownloadSpec]],
    results: dict[str, DownloadResult],
    session: aiohttp.ClientSession,
    semaphore: asyncio.Semaphore,
    max_retries: int,
) -> None:
    while True:
        spec = await queue.get()
        try:
            if spec is None:
                return
            result = results[spec.output]
            await process_spec(session, spec, result, semaphore, max_retries)
        finally:
            queue.task_done()


async def run_downloader(
    specs: list[DownloadSpec],
    report_path: str,
    max_concurrency: int = 5,
    worker_count: int = 8,
    retries: int = 3,
    timeout_seconds: float = 30.0,
) -> list[DownloadResult]:
    if max_concurrency < 1:
        raise ValueError("max_concurrency must be >= 1")
    if worker_count < 1:
        raise ValueError("worker_count must be >= 1")

    queue: asyncio.Queue[Optional[DownloadSpec]] = asyncio.Queue()
    semaphore = asyncio.Semaphore(max_concurrency)

    # Tradeoff: queue + workers decouples scheduling from transfer limits.
    # We also use a semaphore so you can experiment with worker_count independently.
    results = {
        spec.output: DownloadResult(url=spec.url, output=spec.output, expected_sha256=spec.sha256)
        for spec in specs
    }

    for spec in specs:
        set_status(results[spec.output], FileStatus.QUEUED)
        await queue.put(spec)

    timeout = aiohttp.ClientTimeout(total=timeout_seconds)
    connector = aiohttp.TCPConnector(limit=0)

    async with aiohttp.ClientSession(timeout=timeout, connector=connector) as session:
        workers = [
            asyncio.create_task(
                worker_loop(
                    name=f"worker-{idx}",
                    queue=queue,
                    results=results,
                    session=session,
                    semaphore=semaphore,
                    max_retries=retries,
                )
            )
            for idx in range(worker_count)
        ]

        await queue.join()

        for _ in workers:
            await queue.put(None)
        await queue.join()

        await asyncio.gather(*workers)

    ordered_results = [results[spec.output] for spec in specs]
    resolved_report_path = resolve_project_path(report_path)
    await write_report(str(resolved_report_path), ordered_results)
    return ordered_results


def print_summary(results: list[DownloadResult], report_path: str) -> None:
    completed = sum(1 for r in results if r.status == FileStatus.COMPLETED)
    failed = sum(1 for r in results if r.status == FileStatus.FAILED)
    print("\n=== Summary ===")
    print(f"Completed: {completed}")
    print(f"Failed: {failed}")
    print(f"Report: {report_path}")


async def async_main(args: argparse.Namespace) -> int:
    specs = await load_manifest(args.manifest)
    resolved_report_path = resolve_project_path(args.report)
    results = await run_downloader(
        specs=specs,
        report_path=str(resolved_report_path),
        max_concurrency=args.max_concurrency,
        worker_count=args.workers,
        retries=args.retries,
        timeout_seconds=args.timeout_seconds,
    )
    print_summary(results, str(resolved_report_path))
    return 0


def main() -> int:
    args = parse_args()
    try:
        return asyncio.run(async_main(args))
    except KeyboardInterrupt:
        print("Interrupted by user")
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
