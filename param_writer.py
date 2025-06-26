#!/usr/bin/env -S uv run --script

# /// script
#
# ///

import pickle

params_read = "parameters.pickled"
params_write = {
    "user_name": "vek",
    "password": "Fz-25_Vek*",
    "endpoint": "SERVER1/DeviceIpint.134/SourceEndpoint.video:0:0",
    "height": 1080,
    "width": 1920,
}

with open(params_read, "wb") as out_file:
    pickle.dump(params_write, out_file)
