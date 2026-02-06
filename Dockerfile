FROM python:3.11-slim

WORKDIR /app

ENV CREWAI_STORAGE_DIR=ai_corporation

RUN apt-get update && apt-get install -y curl git && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Pre-download ONNX embedding model for faster cold starts
RUN python -c "from chromadb.utils.embedding_functions.onnx_mini_lm_l6_v2 import ONNXMiniLM_L6_V2; ONNXMiniLM_L6_V2()" || echo "ONNX pre-download skipped"

COPY agents/ /app/agents/
COPY crews/ /app/crews/
COPY src/ /app/src/
COPY data/ /app/data/
COPY CLAUDE.md README.md /app/
COPY app.py /app/app.py

CMD streamlit run app.py --server.port=$PORT --server.address=0.0.0.0 --server.headless=true --server.enableCORS=false --server.enableXsrfProtection=false
