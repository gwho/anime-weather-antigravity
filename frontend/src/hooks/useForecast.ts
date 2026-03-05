import { useCallback, useRef, useState } from 'react'

import { APIError, fetchForecastByCity, fetchForecastByCoords } from '../api/forecast'
import type { ForecastResponse } from '../types'

type RequestParams =
  | { mode: 'city'; city: string }
  | { mode: 'coords'; lat: number; lon: number }
  | null

interface UseForecastResult {
  data: ForecastResponse | null
  loading: boolean
  error: string | null
  fetchByCity: (city: string) => Promise<void>
  fetchByCoords: (lat: number, lon: number) => Promise<void>
  retry: () => Promise<void>
}

const toFriendlyError = (error: unknown): string => {
  if (error instanceof APIError) {
    return error.message
  }
  if (error instanceof DOMException && error.name === 'AbortError') {
    return 'The request timed out. Please try again.'
  }
  if (error instanceof TypeError) {
    return 'Network error. Check your connection and try again.'
  }
  if (error instanceof Error) {
    return error.message
  }
  return 'Unexpected error while loading forecast.'
}

export const useForecast = (): UseForecastResult => {
  const [data, setData] = useState<ForecastResponse | null>(null)
  const [loading, setLoading] = useState<boolean>(false)
  const [error, setError] = useState<string | null>(null)
  const lastRequestRef = useRef<RequestParams>(null)

  const fetchByCity = useCallback(async (city: string): Promise<void> => {
    setLoading(true)
    setError(null)
    try {
      const next = await fetchForecastByCity(city)
      setData(next)
      lastRequestRef.current = { mode: 'city', city }
    } catch (err: unknown) {
      setError(toFriendlyError(err))
    } finally {
      setLoading(false)
    }
  }, [])

  const fetchByCoords = useCallback(async (lat: number, lon: number): Promise<void> => {
    setLoading(true)
    setError(null)
    try {
      const next = await fetchForecastByCoords(lat, lon)
      setData(next)
      lastRequestRef.current = { mode: 'coords', lat, lon }
    } catch (err: unknown) {
      setError(toFriendlyError(err))
    } finally {
      setLoading(false)
    }
  }, [])

  const retry = useCallback(async (): Promise<void> => {
    const request = lastRequestRef.current
    if (!request) {
      return
    }

    if (request.mode === 'city') {
      await fetchByCity(request.city)
      return
    }

    await fetchByCoords(request.lat, request.lon)
  }, [fetchByCity, fetchByCoords])

  return { data, loading, error, fetchByCity, fetchByCoords, retry }
}
