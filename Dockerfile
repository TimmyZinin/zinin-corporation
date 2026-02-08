FROM python:3.11-slim

WORKDIR /app

ENV CREWAI_STORAGE_DIR=ai_corporation

RUN apt-get update && apt-get install -y curl git ffmpeg chromium fonts-liberation libcairo2 && rm -rf /var/lib/apt/lists/*

ENV CHROMIUM_FLAGS="--no-sandbox --disable-gpu --headless"
ENV CHROME_BIN=/usr/bin/chromium

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Pre-download ONNX embedding model for faster cold starts
RUN python -c "from chromadb.utils.embedding_functions.onnx_mini_lm_l6_v2 import ONNXMiniLM_L6_V2; ONNXMiniLM_L6_V2()" || echo "ONNX pre-download skipped"

COPY agents/ /app/agents/
COPY crews/ /app/crews/
COPY src/ /app/src/
COPY data/ /app/data/
COPY CLAUDE.md README.md /app/
COPY app.py run_telegram.py run_alexey_bot.py run_yuki_bot.py start.sh /app/

# Config: copy example, actual config comes via env vars or mounted volume
RUN mkdir -p /app/config
COPY config/financial_sources.yaml.example /app/config/financial_sources.yaml.example
# Use example as default if no real config is provided
RUN cp /app/config/financial_sources.yaml.example /app/config/financial_sources.yaml

RUN chmod +x /app/start.sh

CMD ["/app/start.sh"]
