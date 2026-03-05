interface ErrorStateProps {
  message: string
  onRetry: () => void
}

const classifyError = (message: string): { title: string; hint: string } => {
  const lowered = message.toLowerCase()
  if (lowered.includes('network')) {
    return {
      title: 'Connection dropped',
      hint: 'Check your internet and retry when you are back online.',
    }
  }

  if (lowered.includes('denied') || lowered.includes('location access')) {
    return {
      title: 'Location permission denied',
      hint: 'Use the city search above or enable location access in your browser settings.',
    }
  }

  return {
    title: 'Forecast unavailable',
    hint: 'The API responded with an error. Retry in a few seconds.',
  }
}

export const ErrorState = ({ message, onRetry }: ErrorStateProps) => {
  const details = classifyError(message)

  return (
    <section className="error-state" role="alert" aria-live="assertive">
      <h2 className="error-state__title">{details.title}</h2>
      <p className="error-state__message">{message}</p>
      <p className="error-state__hint">{details.hint}</p>
      <button className="error-state__retry" type="button" onClick={onRetry}>
        Retry
      </button>
    </section>
  )
}
