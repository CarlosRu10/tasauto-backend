FROM python:3.11-slim

WORKDIR /app

# Instalar TODAS las dependencias necesarias para Playwright/Chromium
RUN apt-get update && apt-get install -y \
    libnss3 libatk-bridge2.0-0 libdrm2 libxkbcommon0 \
    libgbm1 libasound2 libxshmfence1 libx11-xcb1 \
    libxcomposite1 libxdamage1 libxfixes3 libxrandr2 \
    libpango-1.0-0 libcairo2 libatspi2.0-0 \
    libcups2 libxss1 libxtst6 fonts-liberation \
    libappindicator3-1 libnss3-tools xdg-utils wget \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN playwright install chromium
RUN playwright install-deps chromium

COPY main.py .

EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]

