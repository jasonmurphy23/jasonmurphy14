FROM python:3.10-slim

RUN apt-get update && apt-get install -y \
    wget \
    unzip \
    curl \
    ca-certificates \
    fonts-liberation \
    libasound2 libatk-bridge2.0-0 libatk1.0-0 libcups2 libdbus-1-3 \
    libdrm2 libgbm1 libnspr4 libnss3 libx11-xcb1 libxcomposite1 libxdamage1 libxrandr2 \
    xdg-utils libxss1 libxtst6 libappindicator3-1 libpangocairo-1.0-0 libpango-1.0-0 x11-utils \
    libgbm-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Google Chrome stable terbaru
RUN wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb && \
    dpkg -i google-chrome-stable_current_amd64.deb || apt-get install -fy && \
    rm google-chrome-stable_current_amd64.deb

WORKDIR /app

COPY bot.py .
COPY requirements.txt .
COPY registered_users.json .

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

ENV BOT_TOKEN=""
ENV ADMIN_ID=""

CMD ["python", "bot.py"]
