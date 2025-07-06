#!/usr/bin/env -S uv run --script

# /// script
#
# ///

from ultralytics import YOLO, checks, hub

checks()  # Verify system setup for Ultralytics training

hub.login("7fe52215985bf11d5430b8cb4359c0f6674de4dd6c")

model = YOLO("https://hub.ultralytics.com/models/j1U2fbQFdL7FOuMmXDRy")
results = model.train()
