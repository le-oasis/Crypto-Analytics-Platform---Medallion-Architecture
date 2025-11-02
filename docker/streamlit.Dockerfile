FROM python:3.10-slim

RUN pip install --no-cache-dir \
    streamlit==1.28.0 \
    plotly==5.17.0 \
    pandas==2.1.0 \
    psycopg2-binary==2.9.9

WORKDIR /app

