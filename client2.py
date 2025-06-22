#!/usr/bin/env -S uv run --script

# /// script
#
# ///

import asyncio

import av

uri = "udp://localhost:8766"  # Adjust the WebSocket server URL
str_options = {"codec": "h264"}


async def main() -> None:
    try:
        container = av.open("output.m3u8", mode="r")
        for packet in container.demux():
            print(
                "PTS: "
                + str(packet.pts)
                + " DTS: "
                + str(packet.dts)
                + " Is keyframe = "
                + str(packet.is_keyframe)
            )
            for frame in packet.decode():
                print(frame)
    # if frame.format
    #    frame.to_image().save("frames/frame-%02d.jpg" % frame.index)
    except Exception as e:
        print(f"Приложение получило ошибку: {e}")


asyncio.run(main())
