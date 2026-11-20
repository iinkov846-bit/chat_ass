FROM python:3.11-slim

WORKDIR /app

# Копируем зависимости
COPY requirements.txt .

# Устанавливаем их, игнорируя кэш, чтобы избежать ошибок
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Копируем весь код (включая ваш main.py)
COPY . .

# Запускаем именно main.py!
CMD ["python", "main.py"]
