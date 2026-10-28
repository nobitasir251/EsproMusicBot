
FROM nikolaik/python-nodejs:python3.10-nodejs19-bullseye

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./

RUN pip3 install --upgrade pip \
    && pip3 install -r requirements.txt

COPY . .

RUN chmod +x start

CMD ["bash", "start"]
