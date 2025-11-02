FROM python:3.10-slim

# Avoid interactive prompts
ENV DEBIAN_FRONTEND=noninteractive

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Set a longer timeout and use multiple retries for pip
ENV PIP_DEFAULT_TIMEOUT=200 \
    PIP_RETRIES=10

# Install Python dependencies
RUN pip install --no-cache-dir \
    --timeout=200 \
    --retries=10 \
    streamlit==1.28.0 \
    plotly==5.17.0 \
    pandas==2.1.0 \
    psycopg2-binary==2.9.9

# Copy application code
WORKDIR /app
COPY ./streamlit /app

# Expose Streamlit port
EXPOSE 8501

# Default command
CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
