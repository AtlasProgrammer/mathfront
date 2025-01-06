import os
from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
from flask_cors import CORS
import jwt
import json
import pika  # Импортируем библиотеку для работы с RabbitMQ

app = Flask(__name__)

# Определяем путь к файлу базы данных
BASE_DIR = os.path.dirname(os.path.abspath(__file__))  # Получаем директорию текущего файла
DATABASE_FILE = os.path.join(BASE_DIR, '..', 'instance', 'tasks_data.db')  # Создаем полный путь к файлу базы данных

# Настройка конфигурации
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{DATABASE_FILE}'  # Используем полный путь к файлу
app.config['SECRET_KEY'] = 'your_secret_key'  # Секретный ключ для JWT
db = SQLAlchemy(app)
CORS(app)


# Настройка RabbitMQ
RABBITMQ_HOST = 'rabbitmq'  # Имя сервиса RabbitMQ в Kubernetes
RABBITMQ_QUEUE = 'task_queue'
RABBITMQ_USER = 'admin'
RABBITMQ_PASS = 'password123'


class Task(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    expression = db.Column(db.TEXT, nullable=False)
    point_a = db.Column(db.REAL, nullable=False)
    point_b = db.Column(db.REAL, nullable=False)
    ttl = db.Column(db.Integer, nullable=False)
    status = db.Column(db.TEXT, default='В очереди')  # Статус задачи
    created_at = db.Column(db.DateTime, default=datetime.now)
    completed_at = db.Column(db.DateTime, nullable=True)  # Дата и время завершения задачи
    newton_result = db.Column(db.REAL, nullable=True)  # Результат метода Ньютона
    segment_result = db.Column(db.REAL, nullable=True)  # Результат метода бисекции



# Статичный аккаунт для авторизации
USER_CREDENTIALS = {
    'username': 'admin',
    'password': 'password123'  # Пароль для входа
}

# Генерация JWT токена
def generate_token():
    payload = {
        'username': USER_CREDENTIALS['username'],
        'exp': datetime.utcnow() + timedelta(hours=1)  # Токен действителен 1 час
    }
    token = jwt.encode(payload, app.config['SECRET_KEY'], algorithm='HS256')
    return token

# Проверка JWT токена
def verify_token(token):
    try:
        decoded_token = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
        return decoded_token
    except jwt.ExpiredSignatureError:
        return None  # Токен истек
    except jwt.InvalidTokenError:
        return None  # Неверный токен

@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    username = data.get('username')
    password = data.get('password')

    if username == USER_CREDENTIALS['username'] and password == USER_CREDENTIALS['password']:
        token = generate_token()
        return jsonify({'token': token}), 200
    return jsonify({'message': 'Неверные учетные данные'}), 401

@app.route('/api/tasks', methods=['POST'])
def create_task():
    token = request.headers.get('Authorization')
    if not token:
        return jsonify({'message': 'Отсутствует токен'}), 403

    token = token.split(" ")[1]  # Извлекаем токен из заголовка "Bearer <token>"

    try:
        decoded_token = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
    except jwt.ExpiredSignatureError:
        return jsonify({'message': 'Токен истек'}), 401
    except jwt.InvalidTokenError:
        return jsonify({'message': 'Неверный токен'}), 401

    data = request.json
    expression = data['expression']
    point_a = data['point_a']
    point_b = data['point_b']
    ttl = data['ttl']

    task = Task(expression=expression, point_a=point_a, point_b=point_b, ttl=ttl)
    db.session.add(task)
    db.session.commit()

    # Запускаем выполнение задачи в фоновом режиме
    # process_task(task.id)

    # Отправляем задачу в RabbitMQ
    credentials = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASS)  # Учетные данные для RabbitMQ
    connection = pika.BlockingConnection(pika.ConnectionParameters(host=RABBITMQ_HOST, credentials=credentials))
    channel = connection.channel()
    channel.queue_declare(queue=RABBITMQ_QUEUE, durable=True)

    task_data = {
        'id': task.id,
        'expression': expression,
        'point_a': point_a,
        'point_b': point_b,
        'ttl': ttl
    }
    channel.basic_publish(
        exchange='',
        routing_key=RABBITMQ_QUEUE,
        body=json.dumps(task_data),
        properties=pika.BasicProperties(
            delivery_mode=2,  # Делает сообщение долговечным
        )
    )
    connection.close()

    return jsonify({'task_id': task.id}), 201

@app.route('/api/tasks/<int:task_id>', methods=['GET'])
def get_task(task_id):
    task = Task.query.get(task_id)
    if not task:
        return jsonify({'message': 'Задача не найдена'}), 404

@app.route('/api/tasks', methods=['GET'])
def get_tasks():
    token = request.headers.get('Authorization')
    if not token:
        return jsonify({'message': 'Отсутствует токен'}), 403

    token = token.split(" ")[1]  # Извлекаем токен из заголовка "Bearer <token>"

    try:
        decoded_token = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
    except jwt.ExpiredSignatureError:
        return jsonify({'message': 'Токен истек'}), 401
    except jwt.InvalidTokenError:
        return jsonify({'message': 'Неверный токен'}), 401

    tasks = Task.query.all()
    return jsonify([{
        'id': task.id,
        'status': task.status,
        'expression': task.expression,
        'newton_result': task.newton_result,
        'segment_result': task.segment_result,
        'completed_at': task.completed_at.isoformat() if task.completed_at else None,
        'ttl': task.ttl
    } for task in tasks])

if __name__ == '__main__':
    with app.app_context():  # Создаем контекст приложения
        db.create_all()  # Создание таблиц
    #app.run(debug=True)  # Запуск приложения
    app.run(host='0.0.0.0', port=5000, debug=True)  # Запуск приложения
    