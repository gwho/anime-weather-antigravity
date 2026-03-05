FROM python:3.12.8-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY anime_weather ./anime_weather

EXPOSE 8000

CMD ["uvicorn", "anime_weather.main:app", "--host", "0.0.0.0", "--port", "8000"]
