# Concurrent File Downloader Prototype (Python + Go)

Project folder:
`/Users/jessejames/Documents/Learn Python/anime-weather-antigravity/asyncio-prototype`

This folder now contains:
- Python asyncio prototype (`downloader_asyncio.py`)
- Hardened API contract spec (`api_contract_spec.md`)
- Contract models (`downloader_contract.py`)
- Go migration (`downloader_go.go`)

## Contract-driven request format
Use `sample_batch_request.json` as the primary request format for the hardened model:
- typed job input
- retry policy
- partial download policy
- duplicate filename policy

## Go downloader (migrated design)

### Why this version
- goroutine worker pool for concurrent downloads
- context-based cancellation and per-attempt timeout
- streaming writes to `.part` files to keep memory usage low
- explicit typed error categories
- explicit state-machine transitions and history tracking
- JSON report shape aligned with the hardened contract

### Run
```bash
go run ./downloader_go.go -input sample_batch_request.json -report download_report_go.json -concurrency 5
```

### Build
```bash
go build ./...
```

## Python prototype (original)

### Install
```bash
python -m pip install -r requirements.txt
```

### Run
```bash
python downloader_asyncio.py sample_manifest.json --report download_report.json
```

## Files
- `downloader_go.go`: Go implementation with goroutines + context + streaming
- `sample_batch_request.json`: contract-style input for Go flow
- `api_contract_spec.md`: hardened functional API specification
- `downloader_contract.py`: Pydantic contract/state machine model
