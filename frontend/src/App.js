import React, { useState, useEffect } from 'react';
import axios from 'axios';
import './App.css';

function App() {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [token, setToken] = useState(localStorage.getItem('token') || '');
  const [expression, setExpression] = useState('');
  const [pointA, setPointA] = useState('');
  const [pointB, setPointB] = useState('');
  const [ttl, setTtl] = useState(60);
  const [status, setStatus] = useState('');
  const [tasks, setTasks] = useState([]);

  const handleLogin = async (e) => {
    e.preventDefault();
    try {
      const response = await axios.post('http://127.0.0.1:5000/api/login', { username, password });
      const { token } = response.data;
      localStorage.setItem('token', token);
      setToken(token);
      setIsAuthenticated(true);
    } catch (error) {
      console.error('Ошибка при входе', error);
    }
  };

  const handleLogout = () => {
    localStorage.removeItem('token');
    setToken('');
    setIsAuthenticated(false);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setStatus('Отправка...');
    try {
      const response = await axios.post(
        'http://127.0.0.1:5000/api/tasks',
        { expression, point_a: pointA, point_b: pointB, ttl },
        { headers: { Authorization: `Bearer ${token}` } }
      );
      setStatus(`Задача создана с ID: ${response.data.task_id}`);
      fetchTasks();  // Обновляем список задач
    } catch (error) {
      setStatus('Ошибка при создании задачи');
    }
  };

  const fetchTasks = async () => {
    try {
      const response = await axios.get('http://127.0.0.1:5000/api/tasks', {
        headers: { Authorization: `Bearer ${token}` },
      });
      setTasks(response.data);
    } catch (error) {
      console.error('Ошибка при получении задач', error);
    }
  };

  const refreshTasks = () => {
    fetchTasks();  // Обновляем список задач
  };

  useEffect(() => {
    if (token) {
      setIsAuthenticated(true);
      fetchTasks();
    }
  }, [token]);

  return (
    <div className="bg-gradient-to-b from-black to-purple-900 min-h-screen flex flex-col" style={{ marginTop: '-90px' }}>
      <link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400&display=swap" rel="stylesheet"></link>
      <div className="flex-grow flex items-center justify-center">
        <div className="w-11/12 max-w-5xl bg-gray-800 rounded-lg p-6">
          {!isAuthenticated ? (
            <div className="bg-gray-600 rounded-lg p-4">
              <h2 className="text-white text-center mb-4">Вход</h2>
              <form onSubmit={handleLogin}>
                <input
                  type="text"
                  placeholder="Введите имя пользователя"
                  className="w-full mb-2 p-2 rounded"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  required
                />
                <input
                  type="password"
                  placeholder="Введите пароль"
                  className="w-full mb-4 p-2 rounded"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                />
                <button className="w-full p-2 bg-white rounded">Войти</button>
              </form>
            </div>
          ) : (
            <div>
              <button onClick={handleLogout} className="mb-4 p-2 bg-red-500 rounded">Выйти</button>
              <div className="flex justify-between">
                <div className="w-1/2 bg-gray-600 rounded-lg p-4 mr-4">
                  <h2 className="text-white text-center mb-4"> Ввод данных</h2>
                  <form onSubmit={handleSubmit}>
                    <input
                      type="text"
                      placeholder="Введите уравнение"
                      className="w-full mb-2 p-2 rounded"
                      value={expression}
                      onChange={(e) => setExpression(e.target.value)}
                      required
                    />
                    <input
                      type="text"
                      placeholder="Введите левый край отрезка: A"
                      className="w-full mb-2 p-2 rounded"
                      value={pointA}
                      onChange={(e) => setPointA(e.target.value)}
                      required
                    />
                    <input
                      type="text"
                      placeholder="Введите правый край отрезка: B"
                      className="w-full mb-2 p-2 rounded"
                      value={pointB}
                      onChange={(e) => setPointB(e.target.value)}
                      required
                    />
                    <input
                      type="number"
                      placeholder="Введите TTL задачи"
                      className="w-full mb-4 p-2 rounded"
                      value={ttl}
                      onChange={(e) => setTtl(e.target.value)}
                      required
                    />
                    <button className="w-full p-2 bg-white rounded">Решить</button>
                  </form>
                  <p className="text-red-500 text-center mt-2">{status}</p>
                </div>
                <div className="w-1/2 bg-gray-600 rounded-lg p-4">
                  <h2 className="text-white text-center mb-4">Очередь задач</h2>
                  <button onClick={refreshTasks} className="mb-4 p-2 bg-blue-500 rounded">Обновить задачи</button>
                  <ul className="task-list flex flex-col" style={{ maxHeight: '300px', overflowY: 'auto' }}>
                    {tasks.map((task) => (
                      <li key={task.id} className="task-item bg-gray-700 rounded-lg p-4 text-white mb-2">
                        <strong>ID:</strong> {task.id} <br />
                        <strong>Статус:</strong> {task.status} <br />
                        <strong>Выражение:</strong> {task.expression} <br />
                        <strong>TTL задачи:</strong> {task.ttl} 
                        {task.completed_at && (
                          <>
                            <br />
                            <strong>Результат Ньютона:</strong> {task.newton_result !== null ? task.newton_result : 'Не найден'}
                            <br />
                            <strong>Результат Бисекции:</strong> {task.segment_result !== null ? task.segment_result : 'Не найден'}
                            <br />
                            <strong>Время завершения:</strong> {new Date(task.completed_at).toLocaleString()}
                          </>
                        )}
                      </li>
                    ))}
                  </ul>
                </div>
              </div>
              <div className="mt-6 bg-gray-600 rounded-lg p-4">
                <h2 className="text-white text-center mb-4">Результаты решений</h2>
                <ul className="results-list">
                  {tasks.map((task) => (
                    task.completed_at && (
                      <li key={task.id} className="text-white mb-2">
                        <strong>ID:</strong> {task.id} <strong>Результат Ньютона:</strong> {task.newton_result !== null ? task.newton_result : 'Не найден'}
                        <br /> 
                        <strong>Результат Бисекции:</strong> {task.segment_result !== null ? task.segment_result : 'Не найден'}
                      </li>
                    )
                  ))}
                </ul>
              </div>
            </div>
          )}
        </div>
      </div>
      <footer>
        <div className="background">
          <svg version="1.1" xmlns="http://www.w3.org/2000/svg" xmlnsXlink="http://www.w3.org/1999/xlink" x="0px" y="0px" width="100%" height="100%" viewBox="0 0 1600 900">
            <defs>
              <linearGradient id="bg" x2="0%" y2="100%">
                <stop offset="0%" style={{ stopColor: 'rgba(53, 127, 242, 0.6)' }}></stop>
                <stop offset="100%" style={{ stopColor: 'rgba(38, 89, 190, 0.06)' }}></stop>
              </linearGradient>
              <path id="wave" fill="url(#bg)" d="M-363.852,502.589 c0,0,236.988-41.997,505.475,0 s371.981,38.998,575.971,0s293.985-39.278,505.474,5.859s493.475,48.368,716.963-4.995v560.106H-363.852V502.589z" />
            </defs>
            <g>
              <use xlinkHref="#wave" opacity=".3">
                <animateTransform attributeName="transform" attributeType="XML" type="translate" dur="8s" calcMode="spline" values="270 230; -285 240; 270 230" keyTimes="0; .5; 1" keySplines="0.42, 0, 0.58, 1.0;0.42, 0, 0.58, 1.0" repeatCount="indefinite" />
              </use>
              <use xlinkHref="#wave" opacity=".6">
                <animateTransform attributeName="transform" attributeType="XML" type="translate" dur="6s" calcMode="spline" values="-270 230;243 280;-270 230" keyTimes="0; .6; 1" keySplines="0.42, 0, 0.58, 1.0;0.42, 0, 0.58, 1.0" repeatCount="indefinite" />
              </use>
              <use xlinkHref="#wave" opacity=".9">
                <animateTransform attributeName="transform" attributeType="XML" type="translate" dur="4s" calcMode="spline" values="0 230;-140 260;0 230" keyTimes="0; .4; 1" keySplines="0.42, 0, 0.58, 1.0;0.42, 0, 0.58, 1.0" repeatCount="indefinite" />
              </use>
            </g>
          </svg>
        </div>
        <section>
          <ul className="socials">
            <li><a className="fa-brands fa-facebook"></a></li>
            <li><a className="fa-brands fa-twitter"></a></li>
            <li><a className="fa-brands fa-linkedin"></a></li>
            <li><a className="fa-brands fa-instagram"></a></li>
          </ul>
          <ul className="links">
            <li><a href='/#'>Home</a></li>
            <li><a href='https://github.com/WatchWitch/mathfront'>Github</a></li>
            <li><a href='/team'>Team</a></li>
          </ul>
          <p className="legal">© 2025 All rights reserved</p>
        </section>
      </footer>
    </div>
  );
}

export default App;