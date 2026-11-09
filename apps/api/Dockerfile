FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
ARG INSTALL_AI=false
COPY requirements.txt .
COPY requirements-ai.txt .
RUN pip install --no-cache-dir -r requirements.txt && if [ "$INSTALL_AI" = "true" ]; then pip install --no-cache-dir -r requirements-ai.txt; fi
COPY app ./app
COPY migrations ./migrations
COPY alembic.ini .
EXPOSE 8000
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
