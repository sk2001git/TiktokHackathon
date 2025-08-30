# app/Dockerfile
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /code

# Copy requirements.txt from app folder (build context is ./app)
COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

# Copy everything inside /app into /code/app
COPY . /code/app

EXPOSE 8000

# Run FastAPI via uvicorn
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
