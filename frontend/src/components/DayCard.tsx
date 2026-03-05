import { MOOD_THEMES } from '../config/moods'
import type { DayForecast } from '../types'

interface DayCardProps {
  forecast: DayForecast
  isSelected: boolean
  onClick: () => void
  index: number
}

const formatDayLabel = (isoDate: string, index: number): string => {
  const date = new Date(`${isoDate}T00:00:00`)
  const now = new Date()
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate())
  const target = new Date(date.getFullYear(), date.getMonth(), date.getDate())

  const dayDiff = Math.round((target.getTime() - today.getTime()) / 86_400_000)
  if (dayDiff === 0) {
    return 'Today'
  }
  if (dayDiff === 1) {
    return 'Tomorrow'
  }

  if (index === 0) {
    return 'Today'
  }

  return new Intl.DateTimeFormat(undefined, {
    weekday: 'short',
    month: 'short',
    day: 'numeric',
  }).format(date)
}

export const DayCard = ({ forecast, isSelected, onClick, index }: DayCardProps) => {
  const theme = MOOD_THEMES[forecast.mood]

  return (
    <article
      className={`day-card${isSelected ? ' day-card--selected' : ''}`}
      style={{
        ['--card-accent' as string]: theme.accent,
      }}
    >
      <button
        className="day-card__trigger"
        type="button"
        onClick={onClick}
        aria-expanded={isSelected}
        aria-label={`Open details for ${formatDayLabel(forecast.date, index)}`}
      >
        <div className="day-card__left">
          <span className="day-card__icon" aria-hidden="true">
            {theme.icon}
          </span>
          <div>
            <p className="day-card__date">{formatDayLabel(forecast.date, index)}</p>
            <p className="day-card__summary">{forecast.weather_description}</p>
          </div>
        </div>

        <div className="day-card__right">
          <p className="day-card__temps">
            {Math.round(forecast.temperature_max)}° / {Math.round(forecast.temperature_min)}°
          </p>
          <p className="day-card__precip">Rain {forecast.precipitation_chance}%</p>
        </div>

        <div className="day-card__teaser">
          <img
            src={forecast.anime.image_url}
            alt={forecast.anime.title}
            width={40}
            height={40}
            loading="lazy"
          />
        </div>

        <span className="day-card__arrow" aria-hidden="true">
          {isSelected ? '▲' : '▼'}
        </span>
      </button>
    </article>
  )
}
