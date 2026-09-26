FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PORT=8080
EXPOSE 8080

# Shell form so $PORT (set by Cloud Run) is expanded. Timeout raised from the
# 30s default because the Gemini call plus upstream APIs can be slow.
CMD exec gunicorn --bind 0.0.0.0:$PORT --workers 1 --threads 8 --timeout 90 app:app
