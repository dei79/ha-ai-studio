FROM ubuntu:24.04@sha256:fe81560990fae86dc4743202b2cb4d3df98d0bcf949173cecef15ce1127ef852
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 HA_AI_STUDIO_DATA=/data \
    PATH="/opt/venv/bin:$PATH"
RUN apt-get update \
    && apt-get install -y --no-install-recommends python3 python3-venv ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && python3 -m venv /opt/venv
WORKDIR /app
COPY requirements.lock.txt ./
RUN pip install --no-cache-dir --upgrade pip==26.2.2 \
    && pip install --no-cache-dir -r requirements.lock.txt
COPY LICENSE THIRD_PARTY.md ./
COPY app ./app
EXPOSE 8099
CMD ["python", "-m", "app.server"]
