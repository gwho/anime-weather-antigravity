package main

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"flag"
	"fmt"
	"io"
	"math"
	"math/rand"
	"net"
	"net/http"
	"net/url"
	"os"
	"os/signal"
	"path/filepath"
	"sort"
	"strings"
	"sync"
	"time"
)

type ErrorCategory string

type RetryStrategy string

type PartialDownloadPolicy string

type DuplicateOutputPolicy string

type JobStatus string

const (
	CategoryInvalidURL       ErrorCategory = "invalid_url"
	CategoryTimeout          ErrorCategory = "timeout"
	CategoryChecksumMismatch ErrorCategory = "checksum_mismatch"
	CategoryDiskWriteError   ErrorCategory = "disk_write_error"
	CategoryInputValidation  ErrorCategory = "input_validation"
)

const (
	RetryFixed       RetryStrategy = "fixed"
	RetryExponential RetryStrategy = "exponential"
)

const (
	PartialCleanup   PartialDownloadPolicy = "cleanup"
	PartialResumable PartialDownloadPolicy = "resumable"
)

const (
	DuplicateReject DuplicateOutputPolicy = "reject_request"
)

const (
	StatusReceived    JobStatus = "received"
	StatusQueued      JobStatus = "queued"
	StatusDownloading JobStatus = "downloading"
	StatusRetryWait   JobStatus = "retry_wait"
	StatusVerifying   JobStatus = "verifying"
	StatusCompleted   JobStatus = "completed"
	StatusFailed      JobStatus = "failed"
)

var terminalStatuses = map[JobStatus]struct{}{
	StatusCompleted: {},
	StatusFailed:    {},
}

var allowedTransitions = map[JobStatus]map[JobStatus]struct{}{
	StatusReceived: {
		StatusQueued: {},
		StatusFailed: {},
	},
	StatusQueued: {
		StatusDownloading: {},
		StatusFailed:      {},
	},
	StatusDownloading: {
		StatusVerifying: {},
		StatusRetryWait: {},
		StatusFailed:    {},
	},
	StatusRetryWait: {
		StatusDownloading: {},
		StatusFailed:      {},
	},
	StatusVerifying: {
		StatusCompleted: {},
		StatusFailed:    {},
	},
	StatusCompleted: {},
	StatusFailed:    {},
}

type ChecksumSpec struct {
	Algorithm string `json:"algorithm"`
	Value     string `json:"value"`
}

type RetryPolicy struct {
	MaxRetries       int             `json:"max_retries"`
	Strategy         RetryStrategy   `json:"strategy"`
	BaseDelaySeconds float64         `json:"base_delay_seconds"`
	MaxDelaySeconds  float64         `json:"max_delay_seconds"`
	Jitter           bool            `json:"jitter"`
	RetryOn          []ErrorCategory `json:"retry_on"`
}

type FileJobInput struct {
	JobID          string        `json:"job_id"`
	URL            string        `json:"url"`
	OutputFilename string        `json:"output_filename"`
	Checksum       *ChecksumSpec `json:"checksum,omitempty"`
	TimeoutSeconds float64       `json:"timeout_seconds"`
}

type DownloadBatchRequest struct {
	RequestID             string                `json:"request_id,omitempty"`
	Jobs                  []FileJobInput        `json:"jobs"`
	RetryPolicy           RetryPolicy           `json:"retry_policy"`
	PartialDownloadPolicy PartialDownloadPolicy `json:"partial_download_policy"`
	DuplicateOutputPolicy DuplicateOutputPolicy `json:"duplicate_output_policy"`
}

type DownloadError struct {
	Category  ErrorCategory     `json:"category"`
	Code      string            `json:"code"`
	Message   string            `json:"message"`
	Retryable bool              `json:"retryable"`
	Details   map[string]string `json:"details,omitempty"`
}

type DownloadResult struct {
	RequestID              string         `json:"request_id,omitempty"`
	JobID                  string         `json:"job_id"`
	URL                    string         `json:"url"`
	OutputFilename         string         `json:"output_filename"`
	Status                 JobStatus      `json:"status"`
	AttemptsUsed           int            `json:"attempts_used"`
	BytesDownloaded        int64          `json:"bytes_downloaded"`
	ChecksumExpected       string         `json:"checksum_expected,omitempty"`
	ChecksumComputed       string         `json:"checksum_computed,omitempty"`
	StartedAt              string         `json:"started_at"`
	FinishedAt             string         `json:"finished_at,omitempty"`
	DurationMS             int64          `json:"duration_ms,omitempty"`
	Error                  *DownloadError `json:"error,omitempty"`
	PartialArtifactPresent bool           `json:"partial_artifact_present"`
	StateHistory           []JobStatus    `json:"state_history"`
}

type DownloadBatchResult struct {
	RequestID   string           `json:"request_id,omitempty"`
	SubmittedAt string           `json:"submitted_at"`
	CompletedAt string           `json:"completed_at"`
	Results     []DownloadResult `json:"results"`
}

type categorizedError struct {
	err DownloadError
}

func (e *categorizedError) Error() string {
	return e.err.Message
}

func newCategorizedError(category ErrorCategory, code, message string, retryable bool, details map[string]string) *categorizedError {
	return &categorizedError{err: DownloadError{
		Category:  category,
		Code:      code,
		Message:   message,
		Retryable: retryable,
		Details:   details,
	}}
}

func defaultRequest() DownloadBatchRequest {
	return DownloadBatchRequest{
		RetryPolicy: RetryPolicy{
			MaxRetries:       3,
			Strategy:         RetryExponential,
			BaseDelaySeconds: 1.0,
			MaxDelaySeconds:  30.0,
			Jitter:           true,
			RetryOn:          []ErrorCategory{CategoryTimeout},
		},
		PartialDownloadPolicy: PartialCleanup,
		DuplicateOutputPolicy: DuplicateReject,
	}
}

func loadRequest(path string) (DownloadBatchRequest, error) {
	request := defaultRequest()

	content, err := os.ReadFile(path)
	if err != nil {
		return request, err
	}
	if err := json.Unmarshal(content, &request); err != nil {
		return request, err
	}

	for i := range request.Jobs {
		if request.Jobs[i].TimeoutSeconds <= 0 {
			request.Jobs[i].TimeoutSeconds = 30.0
		}
	}

	return request, nil
}

func normalizeOutputFilename(value string) (string, error) {
	normalized := strings.TrimSpace(strings.ReplaceAll(value, "\\", "/"))
	for strings.HasPrefix(normalized, "./") {
		normalized = strings.TrimPrefix(normalized, "./")
	}

	if normalized == "" {
		return "", errors.New("output_filename cannot be empty")
	}
	if strings.HasSuffix(normalized, "/") {
		return "", errors.New("output_filename must reference a file, not a directory")
	}
	if filepath.IsAbs(normalized) {
		return "", errors.New("output_filename must be a relative path")
	}

	parts := strings.Split(normalized, "/")
	for _, part := range parts {
		if part == ".." {
			return "", errors.New("output_filename cannot contain parent traversal '..'")
		}
	}

	return strings.ToLower(normalized), nil
}

func validateRequest(request DownloadBatchRequest) error {
	if request.PartialDownloadPolicy != PartialCleanup {
		return newCategorizedError(
			CategoryInputValidation,
			"unsupported_partial_policy",
			"partial_download_policy='resumable' is not supported in v1; use 'cleanup'",
			false,
			nil,
		)
	}
	if request.DuplicateOutputPolicy != DuplicateReject {
		return newCategorizedError(
			CategoryInputValidation,
			"unsupported_duplicate_policy",
			"duplicate_output_policy must be 'reject_request' in v1",
			false,
			nil,
		)
	}
	if len(request.Jobs) == 0 {
		return newCategorizedError(CategoryInputValidation, "empty_jobs", "jobs must contain at least one job", false, nil)
	}

	if request.RetryPolicy.MaxRetries < 0 {
		return newCategorizedError(CategoryInputValidation, "invalid_retries", "max_retries must be >= 0", false, nil)
	}
	if request.RetryPolicy.BaseDelaySeconds < 0 || request.RetryPolicy.MaxDelaySeconds <= 0 {
		return newCategorizedError(CategoryInputValidation, "invalid_backoff", "invalid retry backoff values", false, nil)
	}
	if request.RetryPolicy.MaxDelaySeconds < request.RetryPolicy.BaseDelaySeconds {
		return newCategorizedError(CategoryInputValidation, "invalid_backoff", "max_delay_seconds must be >= base_delay_seconds", false, nil)
	}

	seenIDs := make(map[string]struct{}, len(request.Jobs))
	normalizedToJobs := make(map[string][]string)

	for _, job := range request.Jobs {
		if strings.TrimSpace(job.JobID) == "" {
			return newCategorizedError(CategoryInputValidation, "missing_job_id", "job_id is required", false, nil)
		}
		if _, exists := seenIDs[job.JobID]; exists {
			return newCategorizedError(CategoryInputValidation, "duplicate_job_id", "duplicate job_id: "+job.JobID, false, nil)
		}
		seenIDs[job.JobID] = struct{}{}

		parsed, err := url.Parse(job.URL)
		if err != nil || parsed.Scheme == "" || parsed.Host == "" {
			return newCategorizedError(CategoryInvalidURL, "invalid_url", "invalid URL for job_id="+job.JobID, false, nil)
		}
		if parsed.Scheme != "http" && parsed.Scheme != "https" {
			return newCategorizedError(CategoryInvalidURL, "invalid_url_scheme", "URL scheme must be http or https", false, nil)
		}

		normalizedOutput, err := normalizeOutputFilename(job.OutputFilename)
		if err != nil {
			return newCategorizedError(CategoryInputValidation, "invalid_output_filename", err.Error(), false, nil)
		}
		normalizedToJobs[normalizedOutput] = append(normalizedToJobs[normalizedOutput], job.JobID)

		if job.Checksum != nil {
			if strings.ToLower(job.Checksum.Algorithm) != "sha256" {
				return newCategorizedError(CategoryInputValidation, "invalid_checksum_algorithm", "checksum.algorithm must be sha256", false, nil)
			}
			if len(job.Checksum.Value) != 64 {
				return newCategorizedError(CategoryInputValidation, "invalid_checksum_length", "checksum.value must be 64 hex chars", false, nil)
			}
			if _, err := hex.DecodeString(job.Checksum.Value); err != nil {
				return newCategorizedError(CategoryInputValidation, "invalid_checksum_hex", "checksum.value must be hex", false, nil)
			}
		}
	}

	var duplicateRows []string
	for normalized, jobIDs := range normalizedToJobs {
		if len(jobIDs) > 1 {
			sort.Strings(jobIDs)
			duplicateRows = append(duplicateRows, fmt.Sprintf("%s -> %s", normalized, strings.Join(jobIDs, ",")))
		}
	}
	if len(duplicateRows) > 0 {
		sort.Strings(duplicateRows)
		return newCategorizedError(
			CategoryInputValidation,
			"duplicate_output_filename",
			"duplicate output filenames are not allowed: "+strings.Join(duplicateRows, "; "),
			false,
			nil,
		)
	}

	return nil
}

func canTransition(from, to JobStatus) bool {
	nextSet, ok := allowedTransitions[from]
	if !ok {
		return false
	}
	_, ok = nextSet[to]
	return ok
}

func setStatus(result *DownloadResult, next JobStatus) error {
	if result.Status == "" {
		result.Status = next
		result.StateHistory = append(result.StateHistory, next)
		return nil
	}
	if !canTransition(result.Status, next) {
		return fmt.Errorf("illegal job status transition: %s -> %s", result.Status, next)
	}
	result.Status = next
	result.StateHistory = append(result.StateHistory, next)
	return nil
}

func retryAllowed(category ErrorCategory, policy RetryPolicy) bool {
	for _, value := range policy.RetryOn {
		if value == category {
			return true
		}
	}
	return false
}

func computeBackoff(policy RetryPolicy, attempt int) time.Duration {
	base := policy.BaseDelaySeconds
	if base <= 0 {
		base = 1.0
	}
	delaySeconds := base
	if policy.Strategy == RetryExponential {
		delaySeconds = base * math.Pow(2, float64(attempt-1))
	}
	if delaySeconds > policy.MaxDelaySeconds {
		delaySeconds = policy.MaxDelaySeconds
	}
	if policy.Jitter {
		factor := 0.8 + rand.Float64()*0.4
		delaySeconds *= factor
	}
	if delaySeconds < 0 {
		delaySeconds = 0
	}
	return time.Duration(delaySeconds * float64(time.Second))
}

func classifyRequestError(err error) *categorizedError {
	if errors.Is(err, context.DeadlineExceeded) {
		return newCategorizedError(CategoryTimeout, "request_timeout", "request timed out", true, nil)
	}
	if errors.Is(err, context.Canceled) {
		return newCategorizedError(CategoryTimeout, "request_canceled", "request canceled", false, nil)
	}

	var netErr net.Error
	if errors.As(err, &netErr) && netErr.Timeout() {
		return newCategorizedError(CategoryTimeout, "network_timeout", netErr.Error(), true, nil)
	}

	var urlErr *url.Error
	if errors.As(err, &urlErr) {
		if urlErr.Timeout() {
			return newCategorizedError(CategoryTimeout, "network_timeout", urlErr.Error(), true, nil)
		}
		return newCategorizedError(CategoryInvalidURL, "invalid_url", urlErr.Error(), false, nil)
	}

	return newCategorizedError(CategoryInputValidation, "http_request_failed", err.Error(), false, nil)
}

func cleanupTemp(tempPath string) bool {
	err := os.Remove(tempPath)
	if err == nil || errors.Is(err, os.ErrNotExist) {
		return false
	}
	return true
}

func downloadOnce(ctx context.Context, client *http.Client, job FileJobInput) (int64, string, bool, *categorizedError) {
	targetPath := filepath.Clean(job.OutputFilename)
	tempPath := targetPath + ".part"

	if err := os.MkdirAll(filepath.Dir(targetPath), 0o755); err != nil {
		return 0, "", false, newCategorizedError(CategoryDiskWriteError, "mkdir_failed", err.Error(), false, nil)
	}
	_ = os.Remove(tempPath)

	req, err := http.NewRequestWithContext(ctx, http.MethodGet, job.URL, nil)
	if err != nil {
		return 0, "", false, classifyRequestError(err)
	}

	resp, err := client.Do(req)
	if err != nil {
		return 0, "", cleanupTemp(tempPath), classifyRequestError(err)
	}
	defer resp.Body.Close()

	if resp.StatusCode >= 400 {
		if resp.StatusCode == http.StatusRequestTimeout || resp.StatusCode == http.StatusTooManyRequests || resp.StatusCode >= 500 {
			return 0, "", cleanupTemp(tempPath), newCategorizedError(CategoryTimeout, "http_retryable_status", fmt.Sprintf("HTTP %d", resp.StatusCode), true, map[string]string{"http_status": fmt.Sprintf("%d", resp.StatusCode)})
		}
		return 0, "", cleanupTemp(tempPath), newCategorizedError(CategoryInputValidation, "http_non_retryable_status", fmt.Sprintf("HTTP %d", resp.StatusCode), false, map[string]string{"http_status": fmt.Sprintf("%d", resp.StatusCode)})
	}

	file, err := os.Create(tempPath)
	if err != nil {
		return 0, "", cleanupTemp(tempPath), newCategorizedError(CategoryDiskWriteError, "create_file_failed", err.Error(), false, nil)
	}

	hash := sha256.New()
	writer := io.MultiWriter(file, hash)
	buffer := make([]byte, 64*1024)
	bytesWritten, copyErr := io.CopyBuffer(writer, resp.Body, buffer)
	closeErr := file.Close()

	if copyErr != nil {
		catErr := classifyRequestError(copyErr)
		if catErr.err.Category != CategoryTimeout {
			catErr = newCategorizedError(CategoryDiskWriteError, "stream_write_failed", copyErr.Error(), false, nil)
		}
		return bytesWritten, "", cleanupTemp(tempPath), catErr
	}
	if closeErr != nil {
		return bytesWritten, "", cleanupTemp(tempPath), newCategorizedError(CategoryDiskWriteError, "close_file_failed", closeErr.Error(), false, nil)
	}

	computed := hex.EncodeToString(hash.Sum(nil))
	if err := os.Rename(tempPath, targetPath); err != nil {
		return bytesWritten, computed, cleanupTemp(tempPath), newCategorizedError(CategoryDiskWriteError, "rename_failed", err.Error(), false, nil)
	}

	return bytesWritten, computed, false, nil
}

func processJob(ctx context.Context, client *http.Client, policy RetryPolicy, job FileJobInput, result *DownloadResult) {
	start := time.Now().UTC()
	result.StartedAt = start.Format(time.RFC3339Nano)
	_ = setStatus(result, StatusDownloading)

	maxAttempts := policy.MaxRetries + 1
	if maxAttempts < 1 {
		maxAttempts = 1
	}

	for attempt := 1; attempt <= maxAttempts; attempt++ {
		result.AttemptsUsed = attempt

		attemptCtx, cancel := context.WithTimeout(ctx, time.Duration(job.TimeoutSeconds*float64(time.Second)))
		bytesWritten, computedChecksum, partialLeft, attemptErr := downloadOnce(attemptCtx, client, job)
		cancel()

		result.BytesDownloaded = bytesWritten
		if partialLeft {
			result.PartialArtifactPresent = true
		}

		if attemptErr == nil {
			if job.Checksum != nil {
				_ = setStatus(result, StatusVerifying)
				result.ChecksumExpected = strings.ToLower(job.Checksum.Value)
				result.ChecksumComputed = strings.ToLower(computedChecksum)
				if !strings.EqualFold(result.ChecksumExpected, result.ChecksumComputed) {
					attemptErr = newCategorizedError(CategoryChecksumMismatch, "checksum_mismatch", "SHA256 checksum mismatch", false, nil)
				}
			} else {
				result.ChecksumComputed = strings.ToLower(computedChecksum)
			}
		}

		if attemptErr == nil {
			result.Error = nil
			_ = setStatus(result, StatusCompleted)
			end := time.Now().UTC()
			result.FinishedAt = end.Format(time.RFC3339Nano)
			result.DurationMS = end.Sub(start).Milliseconds()
			result.PartialArtifactPresent = false
			return
		}

		result.Error = &attemptErr.err
		allowRetry := attempt < maxAttempts && retryAllowed(attemptErr.err.Category, policy) && attemptErr.err.Retryable
		if allowRetry {
			_ = setStatus(result, StatusRetryWait)
			wait := computeBackoff(policy, attempt)
			select {
			case <-ctx.Done():
				result.Error = &DownloadError{
					Category:  CategoryTimeout,
					Code:      "context_canceled",
					Message:   ctx.Err().Error(),
					Retryable: false,
				}
				_ = setStatus(result, StatusFailed)
				end := time.Now().UTC()
				result.FinishedAt = end.Format(time.RFC3339Nano)
				result.DurationMS = end.Sub(start).Milliseconds()
				return
			case <-time.After(wait):
			}
			_ = setStatus(result, StatusDownloading)
			continue
		}

		_ = setStatus(result, StatusFailed)
		end := time.Now().UTC()
		result.FinishedAt = end.Format(time.RFC3339Nano)
		result.DurationMS = end.Sub(start).Milliseconds()
		return
	}

	if _, isTerminal := terminalStatuses[result.Status]; !isTerminal {
		_ = setStatus(result, StatusFailed)
	}
	end := time.Now().UTC()
	result.FinishedAt = end.Format(time.RFC3339Nano)
	result.DurationMS = end.Sub(start).Milliseconds()
}

type queuedJob struct {
	Job    FileJobInput
	Result *DownloadResult
}

func writeReport(path string, report DownloadBatchResult) error {
	payload, err := json.MarshalIndent(report, "", "  ")
	if err != nil {
		return err
	}
	return os.WriteFile(path, payload, 0o644)
}

func main() {
	inputPath := flag.String("input", "sample_batch_request.json", "Path to batch request JSON")
	reportPath := flag.String("report", "download_report_go.json", "Path to output report JSON")
	concurrency := flag.Int("concurrency", 5, "Maximum concurrent downloads")
	flag.Parse()

	if *concurrency < 1 {
		fmt.Fprintln(os.Stderr, "concurrency must be >= 1")
		os.Exit(2)
	}

	request, err := loadRequest(*inputPath)
	if err != nil {
		fmt.Fprintf(os.Stderr, "failed to load input: %v\n", err)
		os.Exit(1)
	}

	if err := validateRequest(request); err != nil {
		fmt.Fprintf(os.Stderr, "input validation failed: %v\n", err)
		os.Exit(1)
	}

	ctx, cancel := signal.NotifyContext(context.Background(), os.Interrupt)
	defer cancel()

	httpClient := &http.Client{
		Transport: &http.Transport{
			MaxIdleConns:        50,
			MaxIdleConnsPerHost: *concurrency,
			IdleConnTimeout:     30 * time.Second,
		},
	}

	submitted := time.Now().UTC()
	results := make([]DownloadResult, 0, len(request.Jobs))
	queue := make(chan queuedJob)

	var wg sync.WaitGroup
	for i := 0; i < *concurrency; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			for item := range queue {
				processJob(ctx, httpClient, request.RetryPolicy, item.Job, item.Result)
			}
		}()
	}

	for _, job := range request.Jobs {
		result := DownloadResult{
			RequestID:      request.RequestID,
			JobID:          job.JobID,
			URL:            job.URL,
			OutputFilename: job.OutputFilename,
			StateHistory:   make([]JobStatus, 0, 8),
		}
		_ = setStatus(&result, StatusReceived)
		_ = setStatus(&result, StatusQueued)
		results = append(results, result)
		queue <- queuedJob{Job: job, Result: &results[len(results)-1]}
	}
	close(queue)
	wg.Wait()

	report := DownloadBatchResult{
		RequestID:   request.RequestID,
		SubmittedAt: submitted.Format(time.RFC3339Nano),
		CompletedAt: time.Now().UTC().Format(time.RFC3339Nano),
		Results:     results,
	}

	if err := writeReport(*reportPath, report); err != nil {
		fmt.Fprintf(os.Stderr, "failed to write report: %v\n", err)
		os.Exit(1)
	}

	completed := 0
	failed := 0
	for _, result := range results {
		switch result.Status {
		case StatusCompleted:
			completed++
		case StatusFailed:
			failed++
		}
	}

	fmt.Println("=== Summary ===")
	fmt.Printf("Completed: %d\n", completed)
	fmt.Printf("Failed: %d\n", failed)
	fmt.Printf("Report: %s\n", *reportPath)
}
