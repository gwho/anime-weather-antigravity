"""Hardened API contract models for the asyncio downloader prototype.

This module defines:
- request/response data contracts (Pydantic)
- retry policy and execution policy contracts
- job status state machine and transition guards
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from pathlib import PurePosixPath
from typing import Annotated, Optional

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, StringConstraints, field_validator, model_validator


JobId = Annotated[
    str,
    StringConstraints(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$", min_length=1, max_length=64),
]
OutputFilename = Annotated[str, StringConstraints(min_length=1, max_length=1024)]
Sha256Hex = Annotated[str, StringConstraints(pattern=r"^[a-fA-F0-9]{64}$")]


class ErrorCategory(str, Enum):
    INVALID_URL = "invalid_url"
    TIMEOUT = "timeout"
    CHECKSUM_MISMATCH = "checksum_mismatch"
    DISK_WRITE_ERROR = "disk_write_error"
    INPUT_VALIDATION = "input_validation"


class RetryStrategy(str, Enum):
    FIXED = "fixed"
    EXPONENTIAL = "exponential"


class PartialDownloadPolicy(str, Enum):
    CLEANUP = "cleanup"
    RESUMABLE = "resumable"


class DuplicateOutputPolicy(str, Enum):
    REJECT_REQUEST = "reject_request"


class JobStatus(str, Enum):
    RECEIVED = "received"
    QUEUED = "queued"
    DOWNLOADING = "downloading"
    RETRY_WAIT = "retry_wait"
    VERIFYING = "verifying"
    COMPLETED = "completed"
    FAILED = "failed"


TERMINAL_STATUSES = {JobStatus.COMPLETED, JobStatus.FAILED}


# Explicit state machine contract for orchestrator-level guards.
ALLOWED_TRANSITIONS: dict[JobStatus, set[JobStatus]] = {
    JobStatus.RECEIVED: {JobStatus.QUEUED, JobStatus.FAILED},
    JobStatus.QUEUED: {JobStatus.DOWNLOADING, JobStatus.FAILED},
    JobStatus.DOWNLOADING: {JobStatus.VERIFYING, JobStatus.RETRY_WAIT, JobStatus.FAILED},
    JobStatus.RETRY_WAIT: {JobStatus.DOWNLOADING, JobStatus.FAILED},
    JobStatus.VERIFYING: {JobStatus.COMPLETED, JobStatus.FAILED},
    JobStatus.COMPLETED: set(),
    JobStatus.FAILED: set(),
}


def _normalize_output_filename(value: str) -> str:
    normalized = value.strip().replace("\\", "/")
    while normalized.startswith("./"):
        normalized = normalized[2:]

    if not normalized:
        raise ValueError("output_filename cannot be empty")
    if normalized.endswith("/"):
        raise ValueError("output_filename must be a file path, not a directory path")

    path = PurePosixPath(normalized)
    if path.is_absolute():
        raise ValueError("output_filename must be relative, absolute paths are not allowed")
    if any(part == ".." for part in path.parts):
        raise ValueError("output_filename must not include parent-directory traversal '..'")

    # Case-folded comparison avoids platform-specific duplicate collisions.
    return path.as_posix().casefold()


class ChecksumSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    algorithm: str = Field(default="sha256")
    value: Sha256Hex

    @field_validator("algorithm")
    @classmethod
    def validate_algorithm(cls, value: str) -> str:
        if value.lower() != "sha256":
            raise ValueError("Only sha256 is supported in this contract version")
        return "sha256"


class RetryPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    max_retries: int = Field(default=3, ge=0, le=10)
    strategy: RetryStrategy = RetryStrategy.EXPONENTIAL
    base_delay_seconds: float = Field(default=1.0, ge=0.0, le=120.0)
    max_delay_seconds: float = Field(default=30.0, ge=0.1, le=3600.0)
    jitter: bool = True
    retry_on: set[ErrorCategory] = Field(default_factory=lambda: {ErrorCategory.TIMEOUT})

    @model_validator(mode="after")
    def validate_retry_policy(self) -> "RetryPolicy":
        if self.max_delay_seconds < self.base_delay_seconds:
            raise ValueError("max_delay_seconds must be >= base_delay_seconds")

        non_retryable = {ErrorCategory.INVALID_URL, ErrorCategory.CHECKSUM_MISMATCH}
        illegal = self.retry_on.intersection(non_retryable)
        if illegal:
            categories = ", ".join(sorted(category.value for category in illegal))
            raise ValueError(f"Non-retryable categories cannot appear in retry_on: {categories}")
        return self


class FileJobInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_id: JobId
    url: HttpUrl
    output_filename: OutputFilename
    checksum: Optional[ChecksumSpec] = None
    timeout_seconds: float = Field(default=30.0, gt=0.0, le=3600.0)

    @field_validator("output_filename")
    @classmethod
    def validate_output_filename(cls, value: str) -> str:
        _normalize_output_filename(value)
        return value


class DownloadBatchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: Optional[JobId] = None
    jobs: list[FileJobInput] = Field(min_length=1, max_length=1000)
    retry_policy: RetryPolicy = Field(default_factory=RetryPolicy)
    partial_download_policy: PartialDownloadPolicy = PartialDownloadPolicy.CLEANUP
    duplicate_output_policy: DuplicateOutputPolicy = DuplicateOutputPolicy.REJECT_REQUEST

    @model_validator(mode="after")
    def validate_batch_constraints(self) -> "DownloadBatchRequest":
        seen_job_ids: set[str] = set()
        for job in self.jobs:
            if job.job_id in seen_job_ids:
                raise ValueError(f"Duplicate job_id found: {job.job_id}")
            seen_job_ids.add(job.job_id)

        if self.partial_download_policy != PartialDownloadPolicy.CLEANUP:
            raise ValueError(
                "partial_download_policy='resumable' is not supported in contract v1; use 'cleanup'"
            )

        normalized_to_jobs: dict[str, list[str]] = {}
        for job in self.jobs:
            normalized = _normalize_output_filename(job.output_filename)
            normalized_to_jobs.setdefault(normalized, []).append(job.job_id)

        collisions = {path: ids for path, ids in normalized_to_jobs.items() if len(ids) > 1}
        if collisions:
            formatted = "; ".join(
                f"{path} -> {', '.join(job_ids)}" for path, job_ids in sorted(collisions.items())
            )
            raise ValueError(
                "Duplicate output filenames are not allowed under duplicate_output_policy='reject_request': "
                f"{formatted}"
            )

        return self


class DownloadError(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category: ErrorCategory
    code: str = Field(min_length=1, max_length=64)
    message: str = Field(min_length=1, max_length=2048)
    retryable: bool
    details: Optional[dict[str, str]] = None


class AttemptRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    attempt_number: int = Field(ge=1)
    status: JobStatus
    started_at: datetime
    ended_at: Optional[datetime] = None
    error: Optional[DownloadError] = None


class DownloadResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: Optional[JobId] = None
    job_id: JobId
    url: HttpUrl
    output_filename: OutputFilename
    status: JobStatus
    attempts_used: int = Field(ge=1)
    bytes_downloaded: int = Field(ge=0)
    checksum_expected: Optional[Sha256Hex] = None
    checksum_computed: Optional[Sha256Hex] = None
    started_at: datetime
    finished_at: Optional[datetime] = None
    duration_ms: Optional[int] = Field(default=None, ge=0)
    error: Optional[DownloadError] = None
    partial_artifact_present: bool = False
    state_history: list[JobStatus] = Field(default_factory=list, min_length=1)

    @model_validator(mode="after")
    def validate_result_consistency(self) -> "DownloadResult":
        if self.state_history[-1] != self.status:
            raise ValueError("Last element of state_history must equal status")

        if self.status in TERMINAL_STATUSES and self.finished_at is None:
            raise ValueError("finished_at is required for terminal states")

        if self.status == JobStatus.COMPLETED and self.error is not None:
            raise ValueError("Completed result cannot include error")

        if self.status == JobStatus.FAILED and self.error is None:
            raise ValueError("Failed result must include error")

        if self.status == JobStatus.COMPLETED and self.partial_artifact_present:
            raise ValueError("Completed result cannot have partial_artifact_present=true")

        return self


class DownloadBatchResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: Optional[JobId] = None
    submitted_at: datetime
    completed_at: datetime
    results: list[DownloadResult] = Field(min_length=1)

    @property
    def completed_count(self) -> int:
        return sum(1 for result in self.results if result.status == JobStatus.COMPLETED)

    @property
    def failed_count(self) -> int:
        return sum(1 for result in self.results if result.status == JobStatus.FAILED)


def can_transition(from_status: JobStatus, to_status: JobStatus) -> bool:
    return to_status in ALLOWED_TRANSITIONS[from_status]


def assert_transition(from_status: JobStatus, to_status: JobStatus) -> None:
    if not can_transition(from_status, to_status):
        raise ValueError(f"Illegal job status transition: {from_status.value} -> {to_status.value}")


__all__ = [
    "ALLOWED_TRANSITIONS",
    "AttemptRecord",
    "ChecksumSpec",
    "DownloadBatchRequest",
    "DownloadBatchResult",
    "DownloadError",
    "DownloadResult",
    "DuplicateOutputPolicy",
    "ErrorCategory",
    "FileJobInput",
    "JobStatus",
    "PartialDownloadPolicy",
    "RetryPolicy",
    "RetryStrategy",
    "TERMINAL_STATUSES",
    "assert_transition",
    "can_transition",
]
