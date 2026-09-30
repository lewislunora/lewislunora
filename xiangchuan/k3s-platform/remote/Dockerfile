FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1
WORKDIR /app
COPY requirements.txt /app/requirements.txt
RUN pip install -r /app/requirements.txt \
 && useradd -m app
COPY marketing_system /app/marketing_system
COPY docs /app/docs
COPY mcp_server.py /app/mcp_server.py
RUN mkdir -p /app/marketing_system/data && chown -R app:app /app
USER app
EXPOSE 8742 8001
CMD ["uvicorn", "marketing_system.api.server:app", "--host", "0.0.0.0", "--port", "8742"]