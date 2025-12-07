FROM python:3.11-slim

# Evitar buffers y bytecode innecesario
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Dependencias del sistema si las necesitas (pandas, etc.)
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copiar requirements e instalarlos
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el resto del código
COPY . /app

# Puerto (Heroku/Render usan $PORT, pero esto ayuda localmente)
EXPOSE 8000

# Comando por defecto
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
