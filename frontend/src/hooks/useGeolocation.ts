import { useCallback, useState } from 'react'

interface GeoPosition {
  lat: number
  lon: number
}

interface UseGeolocationResult {
  position: GeoPosition | null
  error: string | null
  loading: boolean
  request: () => void
}

const mapGeolocationError = (code: number): string => {
  switch (code) {
    case 1:
      return 'Location access was denied. You can still search by city.'
    case 2:
      return 'Location unavailable. Try again or search by city.'
    case 3:
      return 'Location request timed out. Please try again.'
    default:
      return 'Unable to get your location right now.'
  }
}

export const useGeolocation = (): UseGeolocationResult => {
  const [position, setPosition] = useState<GeoPosition | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState<boolean>(false)

  const request = useCallback((): void => {
    if (!navigator.geolocation) {
      setError('Geolocation is not supported by this browser.')
      return
    }

    setLoading(true)
    setError(null)

    navigator.geolocation.getCurrentPosition(
      (coords) => {
        setPosition({
          lat: coords.coords.latitude,
          lon: coords.coords.longitude,
        })
        setLoading(false)
      },
      (geoError) => {
        setError(mapGeolocationError(geoError.code))
        setLoading(false)
      },
      {
        enableHighAccuracy: true,
        timeout: 10_000,
      },
    )
  }, [])

  return { position, error, loading, request }
}
