from celery import Celery
import sqlite3
from decimal import getcontext
import sympy as sp  
from datetime import datetime
import os

getcontext().prec = 15

# Создаем экземпляр Celery с использованием Redis в качестве брокера
celery = Celery('tasks', broker='redis://redis:6379/0', backend='rpc://redis://redis:6379/0')

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

    if f_a * f_b > 0:
        return None  # Нет корней в интервале

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
            return None  # Невозможно найти производную

        x_n1 = x_n - f_x_n / f_prime_x_n

        if abs(x_n1 - x_n) < tolerance or abs(eval_func(expr, x_n1 )) < tolerance:
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

def insert_task_result(conn, task_id, status, accepted_at, completed_at, expression, newton_result, segment_result):
    cursor = conn.cursor()
    try:
        newton_result = round(newton_result, 3) if newton_result is not None else None
    except:
        newton_result = None  
    try:
        segment_result = round(segment_result, 3) if segment_result is not None else None
    except:
        segment_result = None  

    cursor.execute("""
        UPDATE task
        SET status = ?, completed_at = ?, segment_result = ?, newton_result = ?
        WHERE id = ?
    """, (status, completed_at, segment_result, newton_result, task_id))
    conn.commit()

@celery.task
def process_task(task_id):
    db_path = os.path.join(os.path.dirname(__file__), 'instance', 'tasks_data.db')
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    print(f"Connecting to database at: {db_path}")  # Отладочное сообщение
    

    query = "SELECT expression, point_a, point_b, ttl, created_at FROM task WHERE id = ?"
    cursor.execute(query, (task_id,))
    result = cursor.fetchone()

    if result:
        expression, point_a, point_b, ttl, accepted_at = result
        accepted_at = datetime.strptime(accepted_at, "%Y-%m-%d %H:%M:%S.%f")
    else:
        return None  # Если запись с таким id не найдена

    status = "В процессе"
    completed_at = None  
    newton_result = segment_result = None  
    try:
        expression = preprocess_equation(expression)
        
        interval = find_interval(expression, point_a, point_b)
        if interval is None:
            status = "В заданном диапазоне нет корней"
            insert_task_result(conn, task_id, status, accepted_at, completed_at, expression, newton_result, segment_result)
            return
        elif interval == "error":
            status = "Некорректно написано уравнение"
            insert_task_result(conn, task_id, status, accepted_at, completed_at, expression, newton_result, segment_result)
            conn.close()
            return 

        a, b = interval
        x0 = (a + b) / 2  # Начальная точка для метода Ньютона
        
        root_bisection = bisection_method(expression, a, b)
        root_newton = newton_method(expression, x0)
        end_time = datetime.now()
        elapsed_time = end_time - accepted_at

        if elapsed_time.total_seconds() <= ttl:  # Условие для успешного завершения
            status = "Решено"
            completed_at = end_time  # Устанавливаем время завершения
            segment_result = root_bisection
            newton_result = root_newton
        else:
            status = "Не уложился в TTL"

        insert_task_result(conn, task_id, status, accepted_at, completed_at, expression, newton_result, segment_result)

    except SyntaxError:
        status = "Некорректно написано уравнение"
        insert_task_result(conn, task_id, status, accepted_at, completed_at, expression, newton_result, segment_result)
    except Exception as e:
        status = f"Ошибка: {str(e)}"
        insert_task_result(conn, task_id, status, accepted_at, completed_at, expression, newton_result, segment_result)

    conn.close()