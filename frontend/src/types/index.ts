export type WeatherMood =
  | 'scorching'
  | 'sunny'
  | 'cloudy'
  | 'rainy'
  | 'stormy'
  | 'snowy'
  | 'foggy'

export interface AnimeRecommendation {
  title: string
  japanese_title: string
  image_url: string
  synopsis: string
  quote: string
  quote_character: string
  genre: string
  mood_match_reason: string
  source: string
  external_url: string
}

export interface DayForecast {
  date: string
  weather_code: number
  weather_description: string
  temperature_max: number
  temperature_min: number
  precipitation_chance: number
  mood: WeatherMood
  anime: AnimeRecommendation
}

export interface ForecastResponse {
  location: string
  latitude: number
  longitude: number
  forecasts: DayForecast[]
}

export interface MoodTheme {
  gradient: string
  accent: string
  cardBg: string
  textPrimary: string
  textSecondary: string
  icon: string
  label: string
  particleEffect?: 'rain' | 'snow' | 'none' | 'lightning'
}
