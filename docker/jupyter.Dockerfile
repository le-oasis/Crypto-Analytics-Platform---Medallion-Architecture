FROM python:3.10-slim

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/*

# Install Python packages
RUN pip install --no-cache-dir \
    jupyterlab \
    pandas \
    numpy \
    matplotlib \
    seaborn \
    psycopg2-binary

WORKDIR /notebooks

CMD ["jupyter", "lab", "--ip=0.0.0.0", "--allow-root", "--no-browser"]
