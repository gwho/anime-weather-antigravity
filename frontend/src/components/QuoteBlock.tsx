interface QuoteBlockProps {
  quote: string
  character: string
  animeTitle: string
}

export const QuoteBlock = ({ quote, character, animeTitle }: QuoteBlockProps) => {
  const isSynopsis = character.toLowerCase() === 'synopsis'
  const isGenerated = character.toLowerCase() === 'tagline' || quote.toLowerCase().includes('[generated]')

  return (
    <blockquote className="quote-block" aria-label={`Quote from ${animeTitle}`}>
      <p className="quote-block__text">「{quote.replace('[Generated] ', '')}」</p>
      <footer className="quote-block__meta">
        <span className="quote-block__character">— {character}</span>
        {isSynopsis ? <span className="quote-block__label">Synopsis Line</span> : null}
        {isGenerated ? <span className="quote-block__label">Generated Quip</span> : null}
      </footer>
    </blockquote>
  )
}
