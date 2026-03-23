# Hardened Downloader API Contract (v1)

## 1. Scope
This contract defines the request/response schema and execution semantics for a concurrent file downloader service. It is transport-agnostic but assumes request/response usage equivalent to an HTTP API.

Primary goals:
- Deterministic validation
- Explicit retry behavior
- Stable error categories
- Clear handling of partial files and duplicate outputs

## 2. Functional Specification

### 2.1 Operation
- Client submits a `DownloadBatchRequest` containing one or more file jobs.
- Service validates the full batch before starting execution.
- If validation succeeds, each job is executed with bounded concurrency.
- Service returns a `DownloadBatchResult` with per-job `DownloadResult` entries.

### 2.2 Input Validation Rules
- `jobs` must contain at least 1 job.
- Each job must have:
  - `job_id` unique within the batch
  - valid `url` (`http`/`https`)
  - non-empty `output_filename`
- `output_filename` must not be absolute and must not contain path traversal (`..`).
- Duplicate output filenames are detected after normalization.

Normalization for duplicate checks:
- Strip leading `./`
- Convert `\\` to `/`
- Case-fold for collision detection

### 2.3 Duplicate Output Filename Policy
- v1 policy: `reject_request` only.
- If duplicate normalized output filenames are found, the entire request is rejected as input validation failure before any download starts.

### 2.4 Partial Download Policy
- v1 default and supported policy: `cleanup`.
- Any failed attempt removes temporary partial artifacts (`.part`) before retry or terminal failure.
- `resumable` is defined in schema for forward compatibility but is not supported in v1 execution.

### 2.5 Retry Policy Contract
- `max_retries` means retries after first attempt.
- Total attempts per job = `1 + max_retries`.
- Retry policy fields:
  - `max_retries` (default: `3`)
  - `strategy` (`fixed` or `exponential`, default `exponential`)
  - `base_delay_seconds` (default `1.0`)
  - `max_delay_seconds` (default `30.0`)
  - `jitter` (default `true`)
  - `retry_on` (default `{timeout}`)
- Non-retryable categories in v1:
  - `invalid_url`
  - `checksum_mismatch`

### 2.6 Error Categories
Required categories:
- `invalid_url`
- `timeout`
- `checksum_mismatch`
- `disk_write_error`

Additional category used for contract-level validation:
- `input_validation`

Mapping guidance:
- URL parsing/validation failure -> `invalid_url`
- Network/IO timeout -> `timeout`
- Downloaded checksum != expected checksum -> `checksum_mismatch`
- Filesystem write/open/rename failures -> `disk_write_error`
- Batch schema violations (duplicate filenames, invalid path, etc.) -> `input_validation`

### 2.7 Result Semantics
Each `DownloadResult` contains:
- request/job identity
- source URL + output filename
- final status
- attempts used
- bytes downloaded
- checksum expected/computed
- timing metadata
- optional structured error
- flag indicating whether partial artifact remains

v1 guarantee with `cleanup` policy:
- `partial_artifact_present` is always `false` for terminal states.

## 3. Job Status State Machine

Statuses:
- `received`
- `queued`
- `downloading`
- `retry_wait`
- `verifying`
- `completed` (terminal)
- `failed` (terminal)

Allowed transitions:
- `received -> queued | failed`
- `queued -> downloading | failed`
- `downloading -> verifying | retry_wait | failed`
- `retry_wait -> downloading | failed`
- `verifying -> completed | failed`
- `completed -> (none)`
- `failed -> (none)`

Invalid transitions are contract violations and should be rejected by orchestrator logic.
