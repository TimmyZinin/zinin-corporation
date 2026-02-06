# ========================================
# Dockerfile for AI Corporation
# CrewAI Studio Web Interface
# ========================================

FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy configuration files
COPY agents/ /app/agents/
COPY crews/ /app/crews/
COPY *.yaml /app/ 2>/dev/null || true
COPY *.md /app/ 2>/dev/null || true

# Create a simple Streamlit app for CrewAI
COPY app.py /app/app.py

# Expose Streamlit port
EXPOSE 8501

# Health check
HEALTHCHECK CMD curl --fail http://localhost:8501/_stcore/health || exit 1

# Run Streamlit
CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0", "--server.headless=true"]
