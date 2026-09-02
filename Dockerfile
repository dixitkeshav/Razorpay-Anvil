FROM node:20-slim AS web-build

WORKDIR /web

COPY web/package.json ./
RUN npm install

COPY web/ ./
RUN npm run build

FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml .
COPY src ./src

RUN pip install --no-cache-dir -e .

COPY . .
COPY --from=web-build /web/dist ./web/dist

CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
