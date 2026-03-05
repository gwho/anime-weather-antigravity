import type { DayForecast } from '../types'
import { AnimeDetail } from './AnimeDetail'
import { DayCard } from './DayCard'

interface ForecastListProps {
  forecasts: DayForecast[]
  selectedDay: number | null
  onSelectDay: (index: number) => void
}

export const ForecastList = ({ forecasts, selectedDay, onSelectDay }: ForecastListProps) => {
  return (
    <section className="forecast-list" aria-label="Five day forecast timeline">
      {forecasts.map((forecast, index) => {
        const isSelected = selectedDay === index
        return (
          <div
            key={`${forecast.date}-${forecast.weather_code}`}
            className="forecast-list__item"
            style={{ animationDelay: `${index * 100}ms` }}
          >
            <DayCard
              forecast={forecast}
              index={index}
              isSelected={isSelected}
              onClick={() => onSelectDay(index)}
            />
            <div className={`forecast-list__detail${isSelected ? ' forecast-list__detail--open' : ''}`}>
              {isSelected ? <AnimeDetail anime={forecast.anime} mood={forecast.mood} /> : null}
            </div>
          </div>
        )
      })}
    </section>
  )
}
