#!/usr/bin/env -S uv run --script

# /// script
#
# ///

import pickle

params_read = "parameters.pickled"
params_write = {
    "user_name": "vek",
    "password": "Fz-25_Vek*",
    "endpoint": "SERVER1/DeviceIpint.134/SourceEndpoint.video:0:1",
    "height": 576,
    "width": 704,
}

with open(params_read, "wb") as out_file:
    pickle.dump(params_write, out_file)
