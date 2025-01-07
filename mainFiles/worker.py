import pika
import json
import sqlite3
from decimal import getcontext
import sympy as sp  
from datetime import datetime, timedelta
import logging
import os

getcontext().prec = 15

logging.basicConfig(level=logging.DEBUG)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE_FILE = os.path.join(BASE_DIR, '..', 'instance', 'tasks_data.db')


def eval_func(expr, x):
    try:
        sym_expr = sp.sympify(expr)
        return float(sym_expr.subs('x', x))
    except ZeroDivisionError:
        return float('inf')
    except sp.SympifyError:
        return "error"
    except Exception as e:
        return float('nan')

def bisection_method(expr, a, b, tolerance=0.0001):
    f_a = eval_func(expr, a)
    f_b = eval_func(expr, b)

    if f_a * f_b <= 0:
        return None

    while (b - a) / 2.0 > tolerance:
        c = (a + b) / 2.0
        f_c = eval_func(expr, c)
        if f_c == 0:
            return c
        elif f_a * f_c < 0:
            b = c
            f_b = f_c  
        else:
            a = c
            f_a = f_c  
    return (a + b) / 2.0

def newton_method(expr, x0, tolerance=0.0001):
    def derivative(expr, x):
        h = 1e-5
        return (eval_func(expr, x + h) - eval_func(expr, x)) / h

    x_n = x0
    while True:
        f_x_n = eval_func(expr, x_n)
        f_prime_x_n = derivative(expr, x_n)

        if f_prime_x_n == 0:
            return None

        x_n1 = x_n - f_x_n / f_prime_x_n

        if abs(x_n1 - x_n) < tolerance or abs(eval_func(expr, x_n1)) < tolerance:
            return x_n1

        x_n = x_n1

def find_interval(expr, a, b):
    step = 0.01
    last_value = eval_func(expr, a)
    if last_value == 'error':
        return last_value
    while a <= b:
        current_value = eval_func(expr, a)
        if last_value * current_value < 0:
            return (a, a + step)
        last_value = current_value
        a += step

    return None

def preprocess_equation(equation):
    if '=' in equation:
        left, right = equation.split('=')
        return f'({left}) - ({right})' if right.strip() else left.strip()
    return equation 

def insert_task_result(conn, cursor, task_id, status, accepted_at, completed_at, expression, newton_result, segment_result):
    logging.info("start insert data in database")
    
    try:
        newton_result = round(newton_result, 3) if newton_result is not None else None
    except Exception as e:
        logging.error(f"Ошибка округления newton_result: {e}")
        newton_result = None  

    try:
        segment_result = round(segment_result, 3) if segment_result is not None else None
    except Exception as e:
        logging.error(f"Ошибка округления segment_result: {e}")
        segment_result = None  

    try:
        cursor.execute("""
            UPDATE task  -- Убедитесь, что имя таблицы правильное
            SET status = ?, completed_at = ?, segment_result = ?, newton_result = ?
            WHERE id = ?
        """, (status, completed_at, segment_result, newton_result, task_id))
        
        conn.commit()
        logging.info("Данные успешно обновлены.")
        logging.info(f"Ньютон: {newton_result} Бисекция: {segment_result}")
    except Exception as e:
        logging.error(f"Ошибка выполнения запроса: {e}")
    
    logging.info("Printed data on database")

def process_task(task_data):
    task_id = task_data['id']
    expression = task_data['expression']
    point_a = task_data['point_a']
    point_b = task_data['point_b']
    ttl = task_data['ttl']
    ttl = float(ttl)
    logging.info(f"Processing task: {task_id}")
    logging.info(f"Processing task: {task_data}")

    try:
        conn = sqlite3.connect(DATABASE_FILE)
        if conn is None:
            logging.info("Нет подключения")
        else:
            logging.info("Подключение успешно!")
            cursor = conn.cursor()

        cursor.execute("SELECT * FROM task WHERE id = ?", (task_id,))
        result = cursor.fetchone()
        if not result:
            logging.info(f"Запись с id {task_id} не найдена.")

        accepted_at = datetime.now()
        status = "В процессе"
        completed_at = None  
        newton_result = segment_result = None  

        try:
            expression = preprocess_equation(expression)
            
            interval = find_interval(expression, float(point_a), float(point_b))
            if interval is None:
                status = "В заданном диапазоне нет корней"
                insert_task_result(conn, cursor, task_id, status, accepted_at, completed_at, expression, newton_result, segment_result)
                return
            elif interval == "error":
                status = "Некорректно написано уравнение"
                insert_task_result(conn, cursor, task_id, status, accepted_at, completed_at, expression, newton_result, segment_result)
                return 

            a, b = interval
            x0 = (a + b) / 2  

            newton_result = newton_method(expression, x0)
            segment_result = bisection_method(expression, a, b)
            end_time = datetime.now()

            total_time = (end_time - accepted_at).total_seconds()

            if total_time > ttl:
                status = "Истек TTL"
                insert_task_result(conn, cursor, task_id, status, accepted_at, completed_at, expression, newton_result, segment_result)
            else:
                status = "Завершено"
                completed_at = datetime.now()
                logging.info(f"Задача {task_id} выполнена Ньютон: {newton_result}, Бисекция: {segment_result}")  
        except Exception as e:
            status = f"Ошибка: {str(e)}"
            logging.error(f"Error processing task {task_id}: {str(e)}")
        finally:
            cursor.execute("SELECT * FROM task WHERE id = ?", (task_id,))
            insert_task_result(conn, cursor, task_id, status, accepted_at, completed_at, expression, newton_result, segment_result)
            logging.info(f"Задача {task_id} имеет статус: {status}!")
    except sqlite3.Error as e:
        logging.error(f"Ошибка подключения: {e}")
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

def callback(ch, method, _properties, body):
    task_data = json.loads(body)
    logging.info(f"Received task: {task_data}")
    process_task(task_data)
    ch.basic_ack(delivery_tag=method.delivery_tag)

def main():
    RABBITMQ_DEFAULT_USER = 'admin'
    RABBITMQ_DEFAULT_PASS = 'password123'
    credentials = pika.PlainCredentials(RABBITMQ_DEFAULT_USER, RABBITMQ_DEFAULT_PASS)

    try:
        connection = pika.BlockingConnection(pika.ConnectionParameters(host='rabbitmq', credentials=credentials))
        logging.info("Connected to RabbitMQ")
        channel = connection.channel()
        channel.queue_declare(queue='task_queue', durable=True)
        channel.basic_qos(prefetch_count=1)
        channel.basic_consume(queue='task_queue', on_message_callback=callback)
        print('Ожидание задач. Для выхода нажмите CTRL+C')
        channel.start_consuming()
    except pika.exceptions.AMQPConnectionError as e:
        logging.error(f"Failed to connect to RabbitMQ: {e}")
        exit(1)
    except Exception as e:
        logging.error(f"An unexpected error occurred: {e}")
        exit(1)

if __name__ == '__main__':
    main()