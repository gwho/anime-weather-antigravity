import type { ForecastResponse } from '../types'

export class APIError extends Error {
  public readonly status: number

  public constructor(status: number, message: string) {
    super(message)
    this.name = 'APIError'
    this.status = status
  }
}

const API_BASE = import.meta.env.VITE_API_URL?.trim() || 'http://localhost:8000'
const REQUEST_TIMEOUT_MS = 15_000

const buildUrl = (path: string): string => `${API_BASE}${path}`

const withTimeout = async (input: RequestInfo | URL, init?: RequestInit): Promise<Response> => {
  const controller = new AbortController()
  const timeoutId = window.setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS)

  try {
    const response = await fetch(input, {
      ...init,
      signal: controller.signal,
      headers: {
        Accept: 'application/json',
        ...(init?.headers ?? {}),
      },
    })

    return response
  } finally {
    window.clearTimeout(timeoutId)
  }
}

const parseForecast = async (response: Response): Promise<ForecastResponse> => {
  if (!response.ok) {
    let message = `Request failed with status ${response.status}`
    const payload = (await response.json().catch(() => null)) as { detail?: unknown } | null
    if (payload && typeof payload.detail === 'string' && payload.detail.length > 0) {
      message = payload.detail
    }
    throw new APIError(response.status, message)
  }

  const data = (await response.json()) as ForecastResponse
  return data
}

export const fetchForecastByCity = async (city: string): Promise<ForecastResponse> => {
  const query = new URLSearchParams({ city: city.trim() })
  const response = await withTimeout(buildUrl(`/api/forecast?${query.toString()}`))
  return parseForecast(response)
}

export const fetchForecastByCoords = async (
  lat: number,
  lon: number,
): Promise<ForecastResponse> => {
  const query = new URLSearchParams({ lat: String(lat), lon: String(lon) })
  const response = await withTimeout(buildUrl(`/api/forecast?${query.toString()}`))
  return parseForecast(response)
}
