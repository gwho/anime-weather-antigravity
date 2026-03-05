import { useEffect, useMemo, useState } from 'react'

import { CitySearch } from './components/CitySearch'
import { ErrorState } from './components/ErrorState'
import { ForecastList } from './components/ForecastList'
import { LoadingState } from './components/LoadingState'
import { MoodBackground } from './components/MoodBackground'
import { MOOD_THEMES } from './config/moods'
import { useForecast } from './hooks/useForecast'
import { useGeolocation } from './hooks/useGeolocation'
import type { ForecastResponse, WeatherMood } from './types'

const fallbackMood: WeatherMood = 'cloudy'

const getActiveMood = (
  forecasts: ForecastResponse | null,
  selectedDay: number | null,
): WeatherMood => {
  if (!forecasts || forecasts.forecasts.length === 0) {
    return fallbackMood
  }

  const safeIndex = selectedDay !== null ? selectedDay : 0
  const day = forecasts.forecasts[safeIndex] ?? forecasts.forecasts[0]
  return day.mood
}

const App = () => {
  const { data, loading, error, fetchByCity, fetchByCoords, retry } = useForecast()
  const { position, error: geoError, loading: geoLoading, request } = useGeolocation()

  const [selectedDay, setSelectedDay] = useState<number | null>(0)
  const [city, setCity] = useState<string>('')

  useEffect(() => {
    request()
  }, [request])

  useEffect(() => {
    if (!position) {
      return
    }
    void fetchByCoords(position.lat, position.lon)
    setCity(`${position.lat.toFixed(2)}, ${position.lon.toFixed(2)}`)
    setSelectedDay(0)
  }, [fetchByCoords, position])

  useEffect(() => {
    if (!data) {
      return
    }
    setCity(data.location)
    if (selectedDay !== null && selectedDay >= data.forecasts.length) {
      setSelectedDay(0)
    }
  }, [data, selectedDay])

  const onSearch = async (nextCity: string): Promise<void> => {
    await fetchByCity(nextCity)
    setSelectedDay(0)
  }

  const activeMood = useMemo(() => getActiveMood(data, selectedDay), [data, selectedDay])
  const activeTheme = MOOD_THEMES[activeMood]

  const onSelectDay = (index: number): void => {
    setSelectedDay((prev) => (prev === index ? null : index))
  }

  return (
    <>
      <MoodBackground mood={activeMood} />
      <main
        className="app-shell"
        style={{ ['--accent' as string]: activeTheme.accent }}
      >
        <header className="app-header">
          <p className="app-header__kicker">Anime Weather</p>
          <h1 className="app-header__title">Forecast the day. Pick the perfect anime.</h1>
          <p className="app-header__subtitle">
            Five-day weather snapshots paired with live anime picks, quotes, and mood-matched takes.
          </p>
        </header>

        <CitySearch
          onSearch={(value) => {
            void onSearch(value)
          }}
          onUseLocation={request}
          currentCity={city}
          loading={loading}
          locationLoading={geoLoading}
        />

        {geoError && !data && !loading && <p className="app-geo-hint">{geoError}</p>}

        {loading && !data ? <LoadingState /> : null}

        {error && !data ? (
          <ErrorState
            message={error}
            onRetry={() => {
              void retry()
            }}
          />
        ) : null}

        {!loading && !error && data && data.forecasts.length > 0 ? (
          <ForecastList forecasts={data.forecasts} selectedDay={selectedDay} onSelectDay={onSelectDay} />
        ) : null}

        {!loading && !error && data && data.forecasts.length === 0 ? (
          <section className="app-empty" aria-live="polite">
            <h2>No forecast data returned</h2>
            <p>Try another city or use your current location again.</p>
          </section>
        ) : null}

        {error && data ? (
          <section className="app-inline-error" role="status" aria-live="polite">
            <p>{error}</p>
            <button
              type="button"
              onClick={() => {
                void retry()
              }}
            >
              Retry
            </button>
          </section>
        ) : null}
      </main>
    </>
  )
}

export default App
