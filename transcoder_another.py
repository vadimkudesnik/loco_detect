#!/usr/bin/env -S uv run --scripts

# /// script
#
# ///

# Это программа транскоддер которая получает данные с сервера ТТК и направляет клиенту

import asyncio
import json
import pickle
import uuid
from typing import Optional

import requests
import websockets

params_read = "parameters.pickled"
try:
    with open(params_read, "rb") as in_file:
        parameters = pickle.load(in_file)
except FileNotFoundError:
    print(
        f"Файл {params_read} не найден. Пожалуйста, создайте файл с параметрами или используйте другой файл."
    )
    exit(1)

# Строка с адресом websocket соединения с ТТК сервером
uri_ws = "wss://b2b.videoportal.ttk.ru/ws?auth_token="

# Строка с адресом для аутентификации
url_login = "https://b2b.videoportal.ttk.ru/v1/authentication/authenticate_ex2"

# Строка с данными для аутентификации
login_data = {"user_name": "vek", "password": "Fz-25_Vek*"}

# Строка с ID для камеры
streamId = str(uuid.uuid4())  # Uncomment this line to generate a new UUID each time

# Шаблон сообщения для сервера ТТК для запуска потока
json_camera_string = (
    """
{
    "endpoint": """
    + '"'
    + str(parameters["endpoint"])
    + '"'
    + """,
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

height = int(str(parameters["height"]))
width = int(str(parameters["width"]))

process_ffmpeg_in: Optional[asyncio.subprocess.Process] = None
websocket: Optional[websockets.ClientConnection] = None


# функция получения сообщений от ТТК сервера и передачи их на клиент
async def receive_messages() -> None:
    global process_ffmpeg_in
    global websocket
    print("Запуск процесса получения сообщений от ТТК")
    if websocket is None:
        print("Ошибка: websocket не инициализирован")
        return
    if process_ffmpeg_in is None or process_ffmpeg_in.stdin is None:
        print(
            "Ошибка: process_ffmpeg_in или process_ffmpeg_in.stdin не инициализированы"
        )
        return
    while True:
        try:
            message = await websocket.recv(False)  # Получаем сообщение от ТТК
            iD = message[3:39].decode("utf-8")  # Выделяем ID камеры из сообщения
            if iD == streamId:  # Сверяем ID камеры из сообщения с заданным
                process_ffmpeg_in.stdin.write(message[47:])
                await process_ffmpeg_in.stdin.drain()

        except asyncio.CancelledError:
            print("Процесс получения сообщений от ТТК отменен")
            if process_ffmpeg_in is not None and process_ffmpeg_in.stdin is not None:
                await (
                    send_stop_messages()
                )  # Отправляем на сервер ТТК сообщение о закрытии потока
            break
        except Exception as e:
            print(f"Процесс получения сообщений от ТТК получил ошибку: {e}")
            await send_stop_messages()
            break
    if process_ffmpeg_in.stdin.can_write_eof():
        process_ffmpeg_in.stdin.write_eof()

    process_ffmpeg_in.stdin.close()
    await process_ffmpeg_in.stdin.wait_closed()


# функция отправки стартового сообщения на сервер ТТК
async def send_messages() -> None:
    global websocket
    if websocket is None:
        print("Ошибка: websocket не инициализирован")
        return
    try:
        print("Отправка стартового сообщения на сервер ТТК")
        await websocket.send(
            json_camera_string
        )  # Отправка стартового сообщения на сервер ТТК
        print("Сообщение отправлено")
        await asyncio.sleep(0)  # передача управления циклу event
    except websockets.exceptions.ConnectionClosed:
        print("Отправка стартового сообщения на сервер ТТК отменена")
        return


# функция отправки остановочного сообщения на сервер ТТК
async def send_stop_messages() -> None:
    global websocket
    if websocket is None:
        print("Ошибка: websocket не инициализирован")
        return
    try:
        print("Отправка остановочного сообщения на сервер ТТК")
        await websocket.send(
            json_camera_stop_string
        )  # Отправка остановочного сообщения на сервер ТТК
        print("Сообщение отправлено")
        await asyncio.sleep(0)  # передача управления циклу event
    except websockets.exceptions.ConnectionClosed:
        print("Отправка остановчного сообщения на сервер ТТК отменена")
        return


async def set_ffmpeg_in() -> None:
    global process_ffmpeg_in
    print("Запуск процесса ffmpeg")
    process_ffmpeg_in = await asyncio.create_subprocess_exec(
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-hwaccel",
        "cuda",
        "-probesize",
        "1M",
        "-analyzeduration",
        "1M",
        "-f",
        "mp4",
        "-c:v",
        "h264_cuvid",
        "-r",
        "25",
        "-re",
        "-i",
        "pipe:0",
        "-c:v",
        "h264_nvenc",
        "-movflags",
        "frag_keyframe+empty_moov+faststart+default_base_moof",
        "-b:v",
        "1000M",
        "-f",
        "rtsp",
        "-pix_fmt",
        "rgb24",
        "-s:v",
        str(width) + "x" + str(height),
        "-r",
        "25",
        "-n",
        "-an",
        "-rtsp_transport",
        "tcp",
        "rtsp://localhost:8554/mystream",
        stdin=asyncio.subprocess.PIPE,
    )
    print("Процесс ffmpeg_in запущен")


# Оснавная функция транскоддера
async def process_video() -> None:
    global websocket
    try:
        print("Начало запуска процесса транскоддирования")
        print("Получение токена от сервера ТТК")
        response = requests.post(url_login, json=login_data)  # Отправляем запрос
        json_data = json.loads(json.dumps(response.json()))  # Извлекаем данные
        print("Получен токен:" + json_data["token_value"])
        print("Подключаемся к серверу ТТК")
        try:
            websocket = await websockets.connect(
                uri_ws + json_data["token_value"],
                ping_interval=None,
                ping_timeout=None,
            )  # Подключаемся к серверу ТТК

            print("Подключение к серверу ТТК осуществлено")

            await set_ffmpeg_in()

            receive_task = asyncio.create_task(
                receive_messages()
            )  # Создаем задачу по получению сообщений

            print("Запускаем процесс обмена сообщениями")

            try:
                await send_messages()  # Отправляем стартовое сообщение
                print("Процесс обмена сообщениями запущен")

                await asyncio.gather(
                    receive_task, return_exceptions=True
                )  # Запускаем задачу по получению сообщений

                print("Получение сообщений от сервера ТТК остановлено")
                print("Запускаем процесс остановки сервера")
                tasks = asyncio.all_tasks()
                for task in tasks:
                    print(task.get_name())
                    task.cancel()
                print("Все задачи удалены")
            except asyncio.CancelledError:
                await websocket.close()
                print("Получение сообщений от сервера ТТК отменено")
            except Exception as e:
                await websocket.close()
                print(f"Ошибка получения сообщений от сервера ТТК: {e}")
                return
        except asyncio.CancelledError:
            print("Процесс транскодирования сообщений отменен")
            return
        except Exception as e:
            print(f"Процесс транскодирования сообщений получил ошибку: {e}")
            return
    except asyncio.CancelledError:
        print("Процесс транскодирования сообщений отменен")
        return
    except Exception as e:
        print(f"Процесс транскодирования сообщений получил ошибку: {e}")
        return


async def main() -> None:
    try:
        await process_video()

    except asyncio.CancelledError:
        print("Приложение остановлено")
        return

    except Exception as e:
        print(f"Приложение получило ошибку: {e}")
        return


if __name__ == "__main__":
    asyncio.run(main())
