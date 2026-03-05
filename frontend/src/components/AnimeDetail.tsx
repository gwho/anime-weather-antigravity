import { useMemo, useState } from 'react'

import { MOOD_THEMES } from '../config/moods'
import type { AnimeRecommendation, WeatherMood } from '../types'
import { QuoteBlock } from './QuoteBlock'

interface AnimeDetailProps {
  anime: AnimeRecommendation
  mood: WeatherMood
}

const imageFallback =
  'data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" width="360" height="520"><rect width="100%" height="100%" fill="%2321233a"/><text x="50%" y="50%" font-size="20" fill="%23f2f3ff" dominant-baseline="middle" text-anchor="middle">No Poster</text></svg>'

export const AnimeDetail = ({ anime, mood }: AnimeDetailProps) => {
  const [posterFailed, setPosterFailed] = useState<boolean>(false)
  const theme = MOOD_THEMES[mood]

  const genreTags = useMemo(
    () => anime.genre.split('/').map((segment) => segment.trim()).filter((segment) => segment.length > 0),
    [anime.genre],
  )

  const sourceLabel = anime.source === 'fallback' ? 'Classic pick' : 'Live pick'

  return (
    <section
      className="anime-detail"
      style={{
        ['--accent' as string]: theme.accent,
      }}
    >
      <div className="anime-detail__poster-wrap">
        <img
          className="anime-detail__poster"
          src={posterFailed ? imageFallback : anime.image_url || imageFallback}
          alt={`${anime.title} poster`}
          loading="lazy"
          onError={() => setPosterFailed(true)}
        />
      </div>

      <div className="anime-detail__content">
        <header className="anime-detail__header">
          <div>
            <h3 className="anime-detail__title">{anime.title}</h3>
            {anime.japanese_title ? (
              <p className="anime-detail__japanese" lang="ja">
                {anime.japanese_title}
              </p>
            ) : null}
          </div>
          <span className="anime-detail__source">{sourceLabel}</span>
        </header>

        <div className="anime-detail__tags" aria-label="Genres">
          {genreTags.map((tag) => (
            <span key={tag} className="anime-detail__tag">
              {tag}
            </span>
          ))}
        </div>

        <p className="anime-detail__synopsis">{anime.synopsis}</p>

        <QuoteBlock quote={anime.quote} character={anime.quote_character} animeTitle={anime.title} />

        <p className="anime-detail__reason">{anime.mood_match_reason}</p>

        <a
          className="anime-detail__link"
          href={anime.external_url}
          target="_blank"
          rel="noreferrer"
        >
          Watch on MAL →
        </a>
      </div>
    </section>
  )
}
