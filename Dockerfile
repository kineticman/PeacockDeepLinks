FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install dependencies
RUN pip install --no-cache-dir \
    flask \
    apscheduler \
    requests

# Copy application files
COPY bin/peacock_server.py /app/
COPY bin/peacock_ingest_atom.py /app/
COPY bin/peacock_build_lanes.py /app/
COPY bin/peacock_export_hybrid.py /app/

# Make scripts executable
RUN chmod +x /app/*.py

# Create data directory
RUN mkdir -p /data

# Expose web port (configurable via env)
EXPOSE 6655

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:6655/api/status')"

# Run the server
CMD ["python", "-u", "/app/peacock_server.py"]
