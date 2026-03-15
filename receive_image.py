"""
receive_image.py
Receives JPEG frames over WebSocket, runs a depth model, returns raw float32 depth bytes.

Supported MODEL values:
	"depth_pro"         — Apple Depth Pro (best edges, good for AR occlusion)
	"depth_anything_v2" — Depth Anything V2 large (faster, ~50-100ms on 2070)

Depth Pro setup:
	git clone https://github.com/apple/ml-depth-pro && cd ml-depth-pro && pip install -e .
	bash get_pretrained_models.sh

Depth Anything V2 setup:
	git clone https://github.com/DepthAnything/Depth-Anything-V2
	cd Depth-Anything-V2 && pip install -r requirements.txt
	# download vitl checkpoint from the repo README (~1.3GB), point DA2_CKPT at it

Requirements:
	pip install websockets torch torchvision pillow numpy
"""

import asyncio
import io
import sys
import time
from pathlib import Path

import numpy as np
import torch
import websockets
from PIL import Image

# ── Config ────────────────────────────────────────────────────────────────────
HOST       = "0.0.0.0"
PORT       = 8765
# INFER_SIZE = 512	# lower to 256 for speed, raise to 512 for detail
INFER_SIZE = 518

MODEL = "depth_anything_v2"		# "depth_pro" | "depth_anything_v2"

DEPTH_PRO_CKPT = Path("depth_pro.pt")
DA2_CKPT       = Path("depth_anything_v2_vitl.pth")
DA2_REPO       = Path("Depth-Anything-V2")
# ─────────────────────────────────────────────────────────────────────────────

device = torch.device("cuda")


def load_depth_pro():
	import depth_pro as dp
	print("[init] loading Depth Pro...")
	m, t = dp.create_model_and_transforms(device=device, precision=torch.half)
	m.eval()
	m = torch.compile(m)

	def infer(img: Image.Image) -> np.ndarray:
		inp = t(img.resize((INFER_SIZE, INFER_SIZE), Image.LANCZOS))
		with torch.no_grad():
			pred = m.infer(inp)
		depth = pred["depth"].squeeze().float().cpu().numpy()
		depth -= depth.min()
		depth /= depth.max() + 1e-6
		return depth.astype(np.float32)

	def warmup():
		dummy = Image.fromarray(np.zeros((INFER_SIZE, INFER_SIZE, 3), dtype=np.uint8))
		with torch.no_grad():
			m.infer(t(dummy))

	return infer, warmup


def load_depth_anything_v2():
	sys.path.insert(0, str(DA2_REPO))
	from depth_anything_v2.dpt import DepthAnythingV2

	print("[init] loading Depth Anything V2 large...")
	m = DepthAnythingV2(encoder="vitl", features=256, out_channels=[256, 512, 1024, 1024])
	m.load_state_dict(torch.load(DA2_CKPT, map_location="cpu"))
	m.eval().to(device).half()
	m = torch.compile(m)

	def infer(img: Image.Image) -> np.ndarray:
		img = img.resize((INFER_SIZE, INFER_SIZE), Image.LANCZOS)
		inp = torch.from_numpy(np.array(img)).permute(2, 0, 1).unsqueeze(0)
		inp = inp.half().to(device) / 255.0
		with torch.no_grad():
			depth = m(inp).squeeze().float().cpu().numpy()
		depth -= depth.min()
		depth /= depth.max() + 1e-6
		return depth.astype(np.float32)

	def warmup():
		dummy = Image.fromarray(np.zeros((INFER_SIZE, INFER_SIZE, 3), dtype=np.uint8))
		infer(dummy)

	return infer, warmup


# Load whichever model is configured
if MODEL == "depth_pro":
	_infer, _warmup = load_depth_pro()
elif MODEL == "depth_anything_v2":
	_infer, _warmup = load_depth_anything_v2()
else:
	raise ValueError(f"Unknown model: {MODEL!r}")

print("[init] warming up (first inference compiles CUDA kernels, takes ~20s)...")
_warmup()
print("[init] ready\n")


async def handle(ws):
	print("[ws] client connected")
	try:
		async for msg in ws:
			img = Image.open(io.BytesIO(msg)).convert("RGB")

			t0 = time.perf_counter()
			depth = _infer(img)
			infer_ms = (time.perf_counter() - t0) * 1000

			payload = depth.tobytes()

			t1 = time.perf_counter()
			await ws.send(payload)
			send_ms = (time.perf_counter() - t1) * 1000

			print(f"[perf] inference {infer_ms:.1f}ms | send {send_ms:.1f}ms | depth {depth.shape}")

	except websockets.ConnectionClosed:
		print("[ws] client disconnected")


async def main():
	async with websockets.serve(handle, HOST, PORT, max_size=4 * 1024 * 1024):
		print(f"[server] listening on ws://{HOST}:{PORT}")
		await asyncio.Future()


if __name__ == "__main__":
	asyncio.run(main())