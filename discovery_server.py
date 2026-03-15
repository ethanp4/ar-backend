import socket
import time
import threading

DISCOVERY_PORT  = 47777      # UDP port Unity listens on
BROADCAST_MSG   = b"AR_DEPTH_SERVER"  # Magic bytes Unity looks for
BROADCAST_INTERVAL = 2.0     # Seconds between beacons


def start_discovery_broadcaster(port: int = DISCOVERY_PORT):
	"""
	Broadcast UDP beacon on all interfaces so Unity can discover this machine.
	Blocks forever — run in a daemon thread.
	"""
	sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
	sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
	sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

	# Get this machine's LAN IP to include in the beacon
	try:
		# Connect to a dummy address to find the outbound interface IP
		temp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
		temp.connect(("8.8.8.8", 80))
		local_ip = temp.getsockname()[0]
		temp.close()
	except Exception:
		local_ip = "127.0.0.1"

	# Beacon payload: magic bytes + ":" + IP string
	# Unity parses the IP out of this string
	beacon = BROADCAST_MSG + b":" + local_ip.encode()

	print(f"[Discovery] Broadcasting on UDP {port}  local IP: {local_ip}")

	while True:
		try:
			sock.sendto(beacon, ("<broadcast>", port))
		except Exception as e:
			print(f"[Discovery] Broadcast error: {e}")
		time.sleep(BROADCAST_INTERVAL)