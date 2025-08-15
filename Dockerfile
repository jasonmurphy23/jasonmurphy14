FROM python:3.10-slim

# Install dependencies yang dibutuhkan termasuk yang untuk Chrome
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    apt-transport-https \
    ca-certificates \
    fonts-liberation \
    libasound2 \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libcups2 \
    libdbus-1-3 \
    libdrm2 \
    libgbm1 \
    libnspr4 \
    libnss3 \
    libx11-xcb1 \
    libxcomposite1 \
    libxdamage1 \
    libxrandr2 \
    xdg-utils \
    libxss1 \
    libxtst6 \
    libappindicator3-1 \
    libpangocairo-1.0-0 \
    libpango-1.0-0 \
    x11-utils \
    libgbm-dev \
    unzip \
    curl \
    gnupg2 \
    && rm -rf /var/lib/apt/lists/*

# Download dan pasang Google Chrome stable .deb dari sumber resmi
RUN wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
RUN dpkg -i google-chrome-stable_current_amd64.deb || apt-get install -fy
RUN rm google-chrome-stable_current_amd64.deb

# Pasang ChromeDriver versi sesuai Google Chrome
ENV CHROME_DRIVER_VERSION=131.0.6778.108
RUN wget -q "https://edgedl.me.gvt1.com/edgedl/chrome/chrome-for-testing/${CHROME_DRIVER_VERSION}/linux64/chromedriver-linux64.zip" -O /tmp/chromedriver.zip && \
    unzip /tmp/chromedriver.zip -d /usr/local/bin/ && \
    mv /usr/local/bin/chromedriver-linux64/chromedriver /usr/local/bin/chromedriver && \
    chmod +x /usr/local/bin/chromedriver && \
    rm -rf /tmp/chromedriver.zip /usr/local/bin/chromedriver-linux64

WORKDIR /app

COPY bot.py .
COPY requirements.txt .
COPY registered_users.json .

RUN pip install --no-cache-dir -r requirements.txt

ENV BOT_TOKEN=""
ENV ADMIN_ID=""

CMD ["python", "bot.py"]
