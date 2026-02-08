FROM python:3.10-slim

WORKDIR /app

# 1. 安裝基礎必要工具
RUN apt-get update && apt-get install -y \
    curl \
    gnupg2 \
    unixodbc \
    unixodbc-dev \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# 2. 自動偵測 Debian 版本並安裝微軟 ODBC 驅動 (解決 100/127 報錯)
RUN curl https://packages.microsoft.com/keys/microsoft.asc | gpg --dearmor > /usr/share/keyrings/microsoft-ascii.gpg \
    && echo "deb [arch=amd64 signed-by=/usr/share/keyrings/microsoft-ascii.gpg] https://packages.microsoft.com/debian/$(nproc --all | xargs -I {} echo "11")/prod bullseye main" > /etc/apt/sources.list.d/mssql-release.list \
    && apt-get update \
    && ACCEPT_EULA=Y apt-get install -y msodbcsql17 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

COPY . /app

RUN pip install -r requirements.txt

EXPOSE 5000

CMD ["python", "app.py"]