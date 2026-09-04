# Stage 1: build the embeddable widget.js bundle
FROM node:20-alpine AS widget-build

WORKDIR /widget
COPY widget/package.json widget/package-lock.json* ./
RUN npm install
COPY widget/ ./
RUN npm run build

# Stage 2: the Python app itself
FROM python:3.11-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8000

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
COPY --from=widget-build /widget/dist ./widget/dist

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
