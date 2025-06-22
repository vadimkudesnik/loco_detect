#!/usr/bin/env -S uv run --script

# /// script
#
# ///

# Это программа транскоддер которая получает данные с сервера ТТК и направляет клиенту

import asyncio
import json
import signal

import requests
import websockets
from websockets.asyncio.server import serve

# Строка с адресом websocket соединения с ТТК сервером
uri_ws = "wss://b2b.videoportal.ttk.ru/ws?auth_token="

# Строка с адресом для аутентификации
url_login = "https://b2b.videoportal.ttk.ru/v1/authentication/authenticate_ex2"

# Строка с данными для аутентификации
login_data = {"user_name": "vek", "password": "Fz-25_Vek*"}

# Строка с ID для камеры
streamId = "61372ee3-0ac3-8b46-2b57-1febbd783b2a"

# Шаблон сообщения для сервера ТТК для запуска потока
json_camera_string = (
    """
{
    "endpoint": "SERVER1/DeviceIpint.125/SourceEndpoint.video:0:1",
    "format": "mp4",
    "method": "play",
    "streamId": """
    + '"'
    + streamId
    + '"'
    + """,
    "keyFrames": false,
    "speed": 1,
    "htmlSubtitles": false
}
"""
)

# Шаблон сообщения для сервера ТТК об остановке потока
json_camera_stop_string = (
    """
{
    "method": "stop", 
    "streamId": """
    + '"'
    + streamId
    + '"'
    + """, 
    "format": "mp4"
}
"""
)


# функция получения сообщений от ТТК сервера и передачи их на клиент
async def receive_messages(
    websocket: websockets.ClientConnection,  # соединение с ТТК
    websocket_out: websockets.ServerConnection,  # соединение с клиентом
) -> None:
    print("Запуск процесса получения сообщений от ТТК")
    while True:
        try:
            message = await websocket.recv(False)  # Получаем сообщение от ТТК
            iD = message[3:39].decode("utf-8")  # Выделяем ID камеры из сообщения
            if iD == streamId:  # Сверяем ID камеры из сообщения с заданным
                # Работу с файлом используем только в целях разработки
                # binary_file = open(streamId + ".mp4", "ab")  # Открываем файл для записи
                # binary_file.write(
                #    message[47:]
                # )  # Записываем в конец полученное сообщение без заголовка
                # binary_file.close()  # Закрываем файл
                # ------------------------
                await websocket_out.send(
                    message[47:]
                )  # Отправляем клиенту полученное сообщение без заголовка

        except asyncio.CancelledError:
            print("Процесс получения сообщений от ТТК отменен")
            await send_stop_messages(
                websocket
            )  # Отправляем на сервер ТТК сообщение о закрытии потока
            break
        except Exception as e:
            print(f"Процесс получения сообщений от ТТК получил ошибку: {e}")
            await send_stop_messages(websocket)
            break


# функция отправки стартового сообщения на сервер ТТК
async def send_messages(websocket: websockets.ClientConnection) -> None:
    try:
        print("Отправка стартового сообщения на сервер ТТК")
        # Работу с файлом используем только в целях разработки
        # if os.path.exists(streamId + ".mp4"):
        #    os.remove(streamId + ".mp4")
        # ------------------------
        await websocket.send(
            json_camera_string
        )  # Отправка стартового сообщения на сервер ТТК
        print("Сообщение отправлено")
        await asyncio.sleep(0)  # передача управления циклу event
    except websockets.exceptions.ConnectionClosed:
        print("Отправка стартового сообщения на сервер ТТК отменена")
        signal.raise_signal(signal.SIGINT)


# функция отправки остановочного сообщения на сервер ТТК
async def send_stop_messages(websocket: websockets.ClientConnection) -> None:
    try:
        print("Отправка остановочного сообщения на сервер ТТК")
        await websocket.send(
            json_camera_stop_string
        )  # Отправка остановочного сообщения на сервер ТТК
        print("Сообщение отправлено")
        await asyncio.sleep(0)  # передача управления циклу event
    except websockets.exceptions.ConnectionClosed:
        print("Отправка остановчного сообщения на сервер ТТК отменена")


# Оснавная функция транскоддера
async def process_video(websocket_out: websockets.ServerConnection) -> None:
    try:
        print("Начало запуска процесса транскоддирования")
        print("Получение токена от сервера ТТК")
        response = requests.post(url_login, json=login_data)  # Отправляем запрос
        json_data = json.loads(json.dumps(response.json()))  # Извлекаем данные
        print("Получен токен:" + json_data["token_value"])
        print("Подключаемся к серверу ТТК")
        try:
            async with websockets.connect(
                uri_ws + json_data["token_value"]
            ) as websocket:
                print("Подключение к серверу ТТК осуществлено")
                receive_task = asyncio.create_task(
                    receive_messages(websocket, websocket_out)
                )  # Создаем задачу по получению сообщений
                print("Запускаем процесс обмена сообщениями")
                try:
                    await send_messages(websocket)  # Отправляем стартовое сообщение
                    print("Процесс обмена сообщениями запущен")
                    await asyncio.gather(
                        receive_task, return_exceptions=True
                    )  # Запускаем задачу по получению сообщений
                    print("Получение сообщений от сервера ТТК остановлено")
                    print("Запускаем процесс остановки сервера")
                    # get all tasks
                    tasks = asyncio.all_tasks()
                    # cancel all tasks
                    for task in tasks:
                        # request the task cancel
                        print(task.get_name())
                        task.cancel()
                    print("Все задачи удалены")
                except asyncio.CancelledError:
                    await websocket.close()
                    await websocket_out.close()
                    print("Получение сообщений от сервера ТТК отменено")
                except Exception as e:
                    await websocket.close()
                    await websocket_out.close()
                    print(f"Ошибка получения сообщений от сервера ТТК: {e}")
        except asyncio.CancelledError:
            await websocket.close()
            await websocket_out.close()
            print("Процесс транскодирования сообщений отменен")
        except Exception as e:
            await websocket.close()
            await websocket_out.close()
            print(f"Процесс транскодирования сообщений получил ошибку: {e}")
    except asyncio.CancelledError:
        await websocket.close()
        await websocket_out.close()
        print("Процесс транскодирования сообщений отменен")
    except Exception as e:
        await websocket.close()
        await websocket_out.close()
        print(f"Процесс транскодирования сообщений получил ошибку: {e}")


async def main() -> None:
    try:
        stop = asyncio.get_running_loop().create_future()
        async with serve(process_video, "localhost", 8765):
            await stop

    except asyncio.CancelledError:
        print("Приложение остановлено")

    except Exception as e:
        print(f"Приложение получило ошибку: {e}")


if __name__ == "__main__":
    asyncio.run(main())
