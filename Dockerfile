# Используем официальный образ Python
FROM python:3.9-slim

# Устанавливаем рабочую директорию
WORKDIR /app

# Копируем файлы проекта
COPY MultipleFiles/ ./MultipleFiles/
COPY requirements.txt ./
COPY instance/ ./instance/

# Устанавливаем зависимости
RUN pip install --no-cache-dir -r requirements.txt

# Открываем порт
EXPOSE 500

# Запускаем API
CMD ["python", "MultipleFiles/api.py"]
