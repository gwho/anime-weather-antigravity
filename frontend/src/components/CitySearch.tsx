import { useState } from 'react'
import type { FormEvent, KeyboardEvent } from 'react'

interface CitySearchProps {
  onSearch: (city: string) => void
  onUseLocation: () => void
  currentCity: string
  loading: boolean
  locationLoading: boolean
}

export const CitySearch = ({
  onSearch,
  onUseLocation,
  currentCity,
  loading,
  locationLoading,
}: CitySearchProps): JSX.Element => {
  const [query, setQuery] = useState<string>('')

  const onSubmit = (event: FormEvent<HTMLFormElement>): void => {
    event.preventDefault()
    const city = query.trim()
    if (!city) {
      return
    }
    onSearch(city)
  }

  const onInputKeyDown = (event: KeyboardEvent<HTMLInputElement>): void => {
    if (event.key === 'Escape') {
      setQuery('')
    }
  }

  return (
    <section className="city-search" aria-label="Search location">
      <form className="city-search__form" onSubmit={onSubmit}>
        <label className="sr-only" htmlFor="city-input">
          Search city
        </label>
        <input
          id="city-input"
          className="city-search__input"
          type="text"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          onKeyDown={onInputKeyDown}
          placeholder="Search city..."
          autoComplete="off"
          disabled={loading}
        />
        <button className="city-search__submit" type="submit" disabled={loading}>
          Find Forecast
        </button>
      </form>
      <div className="city-search__meta">
        <p className="city-search__current">Now viewing: {currentCity || 'No city selected yet'}</p>
        <button
          className="city-search__location"
          type="button"
          onClick={onUseLocation}
          disabled={loading || locationLoading}
        >
          {locationLoading ? 'Locating…' : 'Use my location'}
        </button>
      </div>
    </section>
  )
}
