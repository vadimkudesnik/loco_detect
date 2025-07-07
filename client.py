#!/usr/bin/env -S uv run --scripts

# /// script
#
# ///

import asyncio
import io
import pickle
from typing import Any, AsyncGenerator

import numpy as np
import uvicorn
from fastapi import FastAPI
from fastapi.requests import Request
from fastapi.responses import StreamingResponse
from fastapi.templating import Jinja2Templates
from PIL import Image
from ultralytics import YOLO

params_read = "parameters.pickled"
try:
    with open(params_read, "rb") as in_file:
        parameters = pickle.load(in_file)
except FileNotFoundError:
    print(
        f"Файл {params_read} не найден. Пожалуйста, создайте файл с параметрами или используйте другой файл."
    )
    exit(1)

model = YOLO(model="yolo11n.pt", verbose=False)  # Загрузка модели YOLO
source = "rtsp://localhost:8554/mystream"

height = int(str(parameters["height"]))
width = int(str(parameters["width"]))

app = FastAPI()
templates = Jinja2Templates(directory="templates")


@app.get("/")
def index(request: Request) -> Any:
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/video_feed")
async def video_feed() -> StreamingResponse:
    return StreamingResponse(
        read_stream(), media_type="multipart/x-mixed-replace;boundary=frame"
    )


async def start_server() -> None:
    config = uvicorn.Config(app=app, host="0.0.0.0", port=8080, access_log=False)
    server = uvicorn.Server(config=config)
    try:
        await server.serve()
    except asyncio.CancelledError:
        server.force_exit = True
        await server.shutdown()
        raise
    except Exception:
        server.force_exit = True
        await server.shutdown()
        raise


async def read_stream() -> AsyncGenerator[bytes, Any]:
    while True:
        try:
            results = model(source, stream=True, device="cuda", verbose=False)
            try:
                for result in results:
                    annotated_frame = np.array(
                        result.plot(
                            pil=False,
                            labels=True,
                            boxes=True,
                            masks=False,
                            probs=False,
                            show=False,
                            color_mode="class",
                        ),
                        dtype=np.uint8,
                    ).reshape([height, width, 3])[..., ::-1]
                    output = io.BytesIO()

                    Image.fromarray(annotated_frame).save(output, format="JPEG")
                    frame = output.getvalue()
                    output.close()
                    response = (
                        b"--frame\r\n"
                        b"Content-Type: image/jpeg\r\n"
                        b"Content-Length: " + f"{len(frame)}".encode() + b"\r\n"
                        b"\r\n" + frame + b"\r\n\r\n"
                    )
                    try:
                        yield response
                    except Exception:
                        print("Yield Exception")
                        break
            except asyncio.CancelledError:
                break
            except Exception:
                break
        except asyncio.CancelledError:
            break
        except Exception:
            break


async def main() -> None:
    try:
        server_task = asyncio.create_task(start_server())
        await asyncio.gather(server_task, return_exceptions=True)
        tasks = asyncio.all_tasks()
        for task in tasks:
            print(task.get_name())
            task.cancel()
    except asyncio.CancelledError:
        print("Получение сообщений от сервера ТТК отменено")
        raise
    except Exception:
        raise


if __name__ == "__main__":
    asyncio.run(main())
