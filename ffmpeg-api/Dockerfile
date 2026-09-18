FROM python:3.12-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .

RUN mkdir -p /tmp/ffmpeg-jobs

EXPOSE 5000

# 2 workers is plenty for a low-traffic demo tool; ffmpeg itself is the heavy
# lifter and each worker just shells out to it. Timeout matches FFMPEG_TIMEOUT_SECONDS.
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "--timeout", "600", "app:app"]
