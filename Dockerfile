# Backend image for Railway (the Vite frontend deploys separately to Vercel).
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY requirements.txt constraints.txt ./
RUN pip install --no-cache-dir --root-user-action=ignore -r requirements.txt -c constraints.txt

COPY backend ./backend

# Railway injects PORT; mount a volume at /data and point the VIBETRIP_*_DIR /
# VIBETRIP_AUTH_FILE variables there so accounts and uploads survive redeploys.
CMD ["sh", "-c", "uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips='*'"]
