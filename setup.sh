#!/bin/bash
set -e
wget -O depth_anything_v2_vitl.pth https://huggingface.co/depth-anything/Depth-Anything-V2-Large/resolve/main/depth_anything_v2_vitl.pth?download=true 
python3 -m venv ./venv
source ./venv/bin/activate
pip install -r requirements.txt