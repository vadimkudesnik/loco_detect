#!/usr/bin/env -S uv run --script

# /// script
#
# ///

# Это программа транскоддер которая получает данные с сервера ТТК и направляет клиенту

import asyncio
import json
import os
import shutil
import signal

import cv2
import numpy as np
import requests
import websockets

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

height = 576
width = 704


# функция получения сообщений от ТТК сервера и передачи их на клиент
async def receive_messages(
    websocket: websockets.ClientConnection,  # соединение с ТТК
    process: asyncio.subprocess.Process,
) -> None:
    print("Запуск процесса получения сообщений от ТТК")
    assert isinstance(process.stdin, asyncio.StreamWriter)
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
                process.stdin.write(message[47:])
                await process.stdin.drain()

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
    if process.stdin.can_write_eof():
        process.stdin.write_eof()

    process.stdin.close()
    await process.stdin.wait_closed()


async def reader(
    process: asyncio.subprocess.Process,
) -> None:
    assert isinstance(process.stdout, asyncio.StreamReader)
    print("Запуск процесса формирования изображений")
    # тут надо прописать очистку папки frames
    if os.path.exists("frames"):
        shutil.rmtree("frames")
    os.makedirs("frames", exist_ok=True)
    # Создаем папку для сохранения кадров
    try:
        os.makedirs("frames")
    except FileExistsError:
        pass
    index = 0
    while True:
        try:
            # Read raw video frame from stdout as bytes array.
            in_bytes = await process.stdout.readexactly(height * width * 3)

            if not in_bytes:
                break  # Break loop if no more bytes.
            else:
                # Transform the byte read into a NumPy array
                try:
                    in_frame = np.frombuffer(in_bytes, np.uint8).reshape(
                        [height, width, 3]
                    )
                    #  o.flush()
                    cv2.imwrite("frames/frame-" + str(index) + ".jpg", in_frame)
                    index += 1
                except Exception as e:
                    print(e)
                    pass
        except asyncio.CancelledError:
            process.kill()
            try:
                await process.wait()
            except TimeoutError:
                print("Вызов ffpeg не может завершиться")
            print("Процесс формирования изображений отменен")
            break
        except Exception as e:
            print(f"Процесс формирования изображений получил ошибку: {e}")
    print("Процесс формирования изображений завершен")


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
async def process_video() -> None:
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
                process_ffmpeg = await asyncio.create_subprocess_exec(
                    "ffmpeg",
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-probesize",
                    "250K",
                    "-analyzeduration",
                    "1M",
                    "-f",
                    "mp4",
                    "-c:v",
                    "h264",
                    "-re",
                    "-i",
                    "pipe:0",
                    "-b:v",
                    "1000k",
                    "-vf",
                    "setrange=limited",
                    "-f",
                    "rawvideo",
                    "-c:v",
                    "rawvideo",
                    "-pix_fmt",
                    "bgr24",
                    "-s:v",
                    "704x576",
                    "-r",
                    "25",
                    "-n",
                    "-an",
                    "-movflags",
                    "frag_keyframe+empty_moov+faststart+default_base_moof",
                    "pipe:1",
                    stdin=asyncio.subprocess.PIPE,
                    stdout=asyncio.subprocess.PIPE,
                )
                receive_task = asyncio.create_task(
                    receive_messages(websocket, process_ffmpeg)
                )  # Создаем задачу по получению сообщений

                response_task = asyncio.create_task(
                    reader(process_ffmpeg)
                )  # Создаем задачу по получению сообщений

                print("Запускаем процесс обмена сообщениями")
                try:
                    await send_messages(websocket)  # Отправляем стартовое сообщение
                    print("Процесс обмена сообщениями запущен")
                    await asyncio.gather(
                        receive_task, response_task, return_exceptions=True
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

                    print("Получение сообщений от сервера ТТК отменено")
                except Exception as e:
                    await websocket.close()

                    print(f"Ошибка получения сообщений от сервера ТТК: {e}")
        except asyncio.CancelledError:
            await websocket.close()

            print("Процесс транскодирования сообщений отменен")
        except Exception as e:
            await websocket.close()

            print(f"Процесс транскодирования сообщений получил ошибку: {e}")
    except asyncio.CancelledError:
        await websocket.close()

        print("Процесс транскодирования сообщений отменен")
    except Exception as e:
        await websocket.close()

        print(f"Процесс транскодирования сообщений получил ошибку: {e}")


async def main() -> None:
    try:
        await process_video()

    except asyncio.CancelledError:
        print("Приложение остановлено")

    except Exception as e:
        print(f"Приложение получило ошибку: {e}")


if __name__ == "__main__":
    asyncio.run(main())
