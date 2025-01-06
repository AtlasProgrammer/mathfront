import sqlite3
import time
from decimal import Decimal, getcontext
getcontext().prec = 15
def eval_func(expr, x):
    try:
        return eval(expr, {"__builtins__": None, "x": x})
    except ZeroDivisionError:
        return float('inf')  

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
            return None  # Предотвращаем деление на 0

        x_n1 = x_n - f_x_n / f_prime_x_n

        if abs(x_n1 - x_n) < tolerance or abs(eval_func(expr, x_n1)) < tolerance:
            return x_n1

        x_n = x_n1

def find_interval(expr, a, b):
    step = 0.01  # Уменьшите шаг
    last_value = eval_func(expr, a)

    while a <= b:
        current_value = eval_func(expr, a)
        if last_value * current_value < 0:
            return (a, a + step)  # Возвращаем интервал, где происходит изменение знака
        last_value = current_value
        a += step

    return None

def preprocess_equation(equation):
    if '=' in equation:
        left, right = equation.split('=')
        return f'({left}) - ({right})' if right.strip() else left.strip()
    return equation 

def insert_task_result(conn, task_id, status, accepted_at, completed_at, newton_result, segment_result):
    cursor = conn.cursor()
    try:
        newton_result = round(newton_result, 3) if newton_result is not None else None
    except:
        newton_result = None
    try:
        segment_result = round(segment_result, 3) if segment_result is not None else None
    except:
        segment_result = None
    cursor.execute("INSERT INTO TaskResults (task_id, status, accepted_at, completed_at, newton_result, segment_result) VALUES (?, ?, ?, ?, ?, ?)",
                   (task_id, status, accepted_at, completed_at, newton_result, segment_result))
    conn.commit()

def main():
    conn = sqlite3.connect('task_data.db')
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM InformationTaskData")
    tasks = cursor.fetchall()

    for task in tasks:
        task_id, expression, point_a, point_b, ttl = task
        ttl = ttl / 10000.0  # Преобразование TTL из integer в формат для вычисления
        accepted_at = time.time()
        status = "В процессе"
        completed_at = None
        newton_result = segment_result = None

        try:
            expression = preprocess_equation(expression)
            
            # Проверка интервала
            interval = find_interval(expression, point_a, point_b)
            if interval is None:
                status = "В заданном диапазоне нет корней"  # Обновленный статус
                insert_task_result(conn, task_id, status, accepted_at, completed_at, newton_result, segment_result)
                continue

            a, b = interval
            x0 = (a + b) / 2
            
            start_time = time.time()
            root_bisection = bisection_method(expression, a, b)
            root_newton = newton_method(expression, x0)

            end_time = time.time()
            elapsed_time = Decimal(end_time) - Decimal(start_time)
            print(ttl, elapsed_time,end_time,start_time )
            if elapsed_time > ttl:
                status = "Не уложился в TTL"
            else:
                status = "Решено"
                completed_at = end_time
                segment_result = root_bisection
                newton_result = root_newton

            insert_task_result(conn, task_id, status, accepted_at, completed_at, newton_result, segment_result)

        except SyntaxError:  # Обработка синтаксической ошибки
            status = "Некорректно написано уравнение"  # Обновленный статус
            insert_task_result(conn, task_id, status, accepted_at, completed_at, newton_result, segment_result)
        except Exception as e:
            # Перехват любых других исключений
            status = "Ошибка"
            insert_task_result(conn, task_id, status, accepted_at, completed_at, newton_result, segment_result)

    conn.close()

if __name__ == "__main__":
    main()