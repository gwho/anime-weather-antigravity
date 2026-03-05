import type { CSSProperties } from 'react'

import { MOOD_THEMES } from '../config/moods'
import type { WeatherMood } from '../types'

interface MoodBackgroundProps {
  mood: WeatherMood
}

const particleCount: Record<'rain' | 'snow' | 'none' | 'lightning', number> = {
  rain: 26,
  snow: 22,
  none: 12,
  lightning: 10,
}

export const MoodBackground = ({ mood }: MoodBackgroundProps) => {
  const theme = MOOD_THEMES[mood]
  const effect = theme.particleEffect ?? 'none'

  return (
    <div
      className={`mood-background mood-background--${effect} mood-background--${mood}`}
      style={
        {
          '--mood-gradient': theme.gradient,
          '--mood-accent': theme.accent,
        } as CSSProperties
      }
      aria-hidden="true"
    >
      <div className="mood-background__gradient" />
      <div className="mood-background__fog-layer mood-background__fog-layer--one" />
      <div className="mood-background__fog-layer mood-background__fog-layer--two" />
      <div className="mood-background__particles">
        {Array.from({ length: particleCount[effect] }).map((_, index) => (
          <span
            key={`${effect}-${index}`}
            className="mood-background__particle"
            style={
              {
                '--particle-x': `${(index * 11) % 100}%`,
                '--particle-delay': `${(index % 7) * 0.8}s`,
                '--particle-duration': `${3.2 + (index % 5) * 0.55}s`,
              } as CSSProperties
            }
          />
        ))}
      </div>
      <div className="mood-background__flash" />
      <div className="mood-background__shimmer" />
    </div>
  )
}
