


"""
send_image.py
Simulates Unity FrameStreamer.cs — reads INPUT_IMAGE from disk, downscales it
to (INPUT_W x INPUT_H), re-encodes as JPEG, and sends over WebSocket.
Depth response dimensions are inferred automatically from the returned bytes.

Requirements:
	pip install websockets pillow numpy
"""

import asyncio
import io
from pathlib import Path
import sys

import numpy as np
import websockets
from PIL import Image, ImageOps

# ── Config ────────────────────────────────────────────────────────────────────
SERVER_URI   = "ws://localhost:8765"
INPUT_IMAGE  = Path(__file__).parent / "example.jpg"

# What we send to the server (should match what the model expects as input)
INPUT_W = 240  # width  — smaller for portrait
INPUT_H = 320  # height — larger for portrait
JPEG_QUALITY = 60

# Streaming cadence
FRAME_SKIP   = 2        # send every Nth tick
TICK_RATE    = 1 / 30   # simulated ~30fps
# ─────────────────────────────────────────────────────────────────────────────


def load_and_encode_frame(path: Path) -> bytes:
	with Image.open(path) as img:
		img = ImageOps.exif_transpose(img)  # honour EXIF rotation before anything else
		img = img.convert("RGB").resize((INPUT_W, INPUT_H), Image.LANCZOS)
		
		buf = io.BytesIO()
		img.save(buf, format="JPEG", quality=JPEG_QUALITY)
		return buf.getvalue()


def depth_received(raw: bytes):
	depth = np.frombuffer(raw, dtype=np.float32)
	n = len(depth)

	side = int(round(n ** 0.5))
	if side * side == n:
		depth = depth.reshape(side, side)
	else:
		# Non-square — e.g. 518×518 padded or different aspect ratio
		# Try common aspect ratios or just display as-is
		print(f"[depth] {n} floats — not square, got {side}²={side*side}, trying fallback")
		# For DA2 with INFER_SIZE=518, output is always 518×518 so this shouldn't hit
		depth = depth.reshape(side, side + (n - side*side))  # rough fallback

	out_path = Path(__file__).parent / "depth.png"
	Image.fromarray((depth * 255).astype(np.uint8)).save(out_path)
	print(f"[depth] saved {depth.shape[0]}×{depth.shape[1]} depth map → {out_path}")


async def stream_frames():
	if not INPUT_IMAGE.exists():
		raise FileNotFoundError(f"Could not find {INPUT_IMAGE}")

	jpg_payload = load_and_encode_frame(INPUT_IMAGE)
	print(f"[init] frame encoded — {len(jpg_payload)} bytes ({INPUT_W}×{INPUT_H} JPEG q{JPEG_QUALITY})")

	frame_counter = 0

	async with websockets.connect(SERVER_URI, max_size=4 * 1024 * 1024) as ws:
		print(f"[ws] connected to {SERVER_URI}")

		async def receive_loop():
			try:
				async for message in ws:
					if isinstance(message, bytes):
						depth_received(message)
					else:
						print(f"[ws] text message: {message}")
			except Exception as e:
				print(f"[receive_loop] error: {e}")
				raise  # re-raise so the task failure is visible

		recv_task = asyncio.create_task(receive_loop())

		try:
			while True:
				await asyncio.sleep(TICK_RATE)
				frame_counter += 1
				if frame_counter % FRAME_SKIP != 0:
					continue
				await ws.send(jpg_payload)
				print(f"[ws] sent frame #{frame_counter} ({len(jpg_payload)} bytes)")

		except (websockets.ConnectionClosed, KeyboardInterrupt):
			print("[ws] connection closed or interrupted")
		finally:
			recv_task.cancel()


if __name__ == "__main__":
	try:
		asyncio.run(stream_frames())
	except FileNotFoundError as e:
		print(f"[error] {e}")
	except OSError as e:
		print(f"[error] could not connect — is the server running on {SERVER_URI}?\n  {e}")