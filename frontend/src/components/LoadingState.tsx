import { useEffect, useState } from 'react'

const loadingMessages = [
  'Mapping clouds to anime arcs…',
  'Syncing weather moods with your watchlist…',
  'Asking the forecast for its main character energy…',
]

export const LoadingState = () => {
  const [messageIndex, setMessageIndex] = useState<number>(0)

  useEffect(() => {
    const timer = window.setInterval(() => {
      setMessageIndex((prev) => (prev + 1) % loadingMessages.length)
    }, 1800)

    return () => window.clearInterval(timer)
  }, [])

  return (
    <section className="loading-state" aria-live="polite" aria-busy="true">
      <p className="loading-state__message">{loadingMessages[messageIndex]}</p>
      <div className="loading-state__stack">
        {Array.from({ length: 5 }).map((_, index) => (
          <article key={`skeleton-${index}`} className="loading-state__card">
            <div className="loading-state__line loading-state__line--icon" />
            <div className="loading-state__line loading-state__line--wide" />
            <div className="loading-state__line loading-state__line--mid" />
            <div className="loading-state__line loading-state__line--thumb" />
          </article>
        ))}
      </div>
    </section>
  )
}
