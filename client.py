#!/usr/bin/env -S uv run --script

# /// script
#
# ///

import asyncio
import gc

import cv2
import numpy as np
import websockets

uri = "ws://localhost:8765"  # Adjust the WebSocket server URL
height = 576
width = 704
ALL_TASKS = set()


def create_task_helper(coroutine):
    # wrap and schedule the coroutine
    task = asyncio.create_task(coroutine)
    # store in collection of all tasks
    global ALL_TASKS
    ALL_TASKS.add(task)
    # add a callback to remove from the collection
    task.add_done_callback(ALL_TASKS.discard)
    # return the task that was created
    return task


async def get_message(websocket: websockets.ClientConnection) -> bytes:
    return await websocket.recv(decode=False)


async def writer(
    websocket: websockets.ClientConnection,
    process: asyncio.subprocess.Process,
) -> None:
    print("Recieve")
    assert isinstance(process.stdin, asyncio.StreamWriter)
    # for j in range(100):
    while True:
        try:
            msg = await get_message(websocket)
            process.stdin.write(msg)
            await process.stdin.drain()
        except:
            await websocket.close()
            print("IN Canceled")
            break

    if process.stdin.can_write_eof():
        process.stdin.write_eof()

    process.stdin.close()
    await process.stdin.wait_closed()
    print("IN Exit")


async def reader(
    process: asyncio.subprocess.Process,
) -> None:
    assert isinstance(process.stdout, asyncio.StreamReader)
    print("Get")
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
        except:
            print("OUT Canceled")
            break
    process.stdout.close()
    await process.stdout.wait_closed()
    print("OUT Exit")


async def main() -> None:
    try:
        async with websockets.connect(uri) as websocket:
            try:
                process_ffmpeg = await asyncio.create_subprocess_exec(
                    "ffmpeg",
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

                try:
                    receive_task = asyncio.create_task(
                        writer(websocket, process_ffmpeg)
                    )
                    response_task = asyncio.create_task(reader(process_ffmpeg))
                    await asyncio.gather(
                        receive_task, response_task, return_exceptions=True
                    )
                except:
                    pass

                await asyncio.sleep(0)

                try:
                    await websocket.close()
                except:
                    pass
                try:
                    await asyncio.wait_for(await process_ffmpeg.wait(), timeout=10.0)
                except TimeoutError:
                    process_ffmpeg.kill()
                    print("timeout!")
                    pass

                print("Done")

            except:
                receive_task.cancel()
                response_task.cancel()
                try:
                    await asyncio.wait_for(await process_ffmpeg.wait(), timeout=10.0)
                except TimeoutError:
                    process_ffmpeg.kill()
                    print("timeout!")
                    pass
                try:
                    await websocket.close()
                except:
                    pass
                await asyncio.sleep(0)
                pass
            try:
                await websocket.close()
            except:
                pass
            await asyncio.sleep(0)
            print("Main end succesfull")
    except:
        pass


if __name__ == "__main__":
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(main())
    except:
        print("Canceled")
    finally:
        loop.close()
        gc.collect()
        print("Exit")
