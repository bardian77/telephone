# Serves the API (and, if built, the static site) in one container. No GPU.
FROM python:3.12-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends tesseract-ocr libgl1 libglib2.0-0 && rm -rf /var/lib/apt/lists/*
COPY pyproject.toml README.md ./
COPY telephone ./telephone
COPY api ./api
COPY experiments ./experiments
RUN pip install --no-cache-dir -e ".[api,providers]" \
 && pip install --no-cache-dir torch torchvision --index-url https://download.pytorch.org/whl/cpu \
 && pip install --no-cache-dir -e ".[metrics]"
COPY web/dist ./web/dist
COPY web/public/data ./web/public/data
ENV TELEPHONE_LIVE=0
EXPOSE 8000
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
