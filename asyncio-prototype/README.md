# Asyncio Concurrent File Downloader (Prototype)

Learning-oriented prototype for downloading many files concurrently using `asyncio`.

## Features
- Input manifest of file URLs and output filenames
- Concurrent downloads with configurable max concurrency (default `5`)
- Per-file status transitions: `queued`, `downloading`, `completed`, `failed`
- Retries transient failures up to 3 times (configurable)
- Optional SHA256 verification
- Chunked streaming to avoid loading entire files into memory
- Final JSON report with metadata and outcomes

## Install
```bash
python -m pip install aiohttp aiofiles
```

## Manifest format
`sample_manifest.json` shows the expected format:

```json
[
  {
    "url": "https://example.com/file.zip",
    "output": "downloads/file.zip",
    "sha256": "optional_hex_digest"
  }
]
```

## Run
```bash
python downloader_asyncio.py sample_manifest.json --report download_report.json
```

Useful flags:
- `--max-concurrency 5`
- `--workers 8`
- `--retries 3`
- `--timeout-seconds 30`

## Design notes
- Queue + worker tasks keep scheduling simple and explicit for learning.
- A semaphore limits true in-flight transfers so worker count can be tuned independently.
- Temporary `.part` files reduce risk of leaving corrupted final outputs.
- Retry logic uses linear backoff for readability over optimal production behavior.
