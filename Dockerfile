FROM python:3.11-slim-bookworm

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && pip uninstall -y opencv-python 2>/dev/null || true \
    && pip install --no-cache-dir opencv-python-headless

COPY . .

ENV DEPLOY_HEADLESS=true
ENV PYTHONUNBUFFERED=1
ENV QT_QPA_PLATFORM=offscreen

# Headless worker — no live feed window, ML + SMS only
CMD ["python", "-u", "violence_monitor.py", "--headless"]
