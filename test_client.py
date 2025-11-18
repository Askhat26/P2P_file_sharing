import requests
import socket
import json
import threading
import os
from concurrent.futures import ThreadPoolExecutor
import hashlib
import argparse

TRACKER_URL = "http://127.0.0.1:5000"
CHUNK_SIZE = 1024 * 1024  # 1 MB

def get_local_ip():
    return socket.gethostbyname(socket.gethostname())

def compute_file_hash(file_path):
    hasher = hashlib.sha1()
    with open(file_path, "rb") as f:
        while chunk := f.read(8192):
            hasher.update(chunk)
    return hasher.hexdigest()

def split_into_chunks(file_path):
    file_size = os.path.getsize(file_path)
    num_chunks = (file_size + CHUNK_SIZE - 1) // CHUNK_SIZE
    return file_size, list(range(num_chunks))

# ------------------------------
# Simple TCP server to serve chunks
# ------------------------------
def serve_chunks(port, file_path):
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind(("0.0.0.0", port))
    server.listen(5)
    print(f"📡 Serving file on port {port}")

    while True:
        conn, addr = server.accept()
        request = conn.recv(1024).decode()

        # Expected: "GET_CHUNK <chunk_id>"
        if request.startswith("GET_CHUNK"):
            _, chunk_id = request.split()
            chunk_id = int(chunk_id)

            with open(file_path, "rb") as f:
                f.seek(chunk_id * CHUNK_SIZE)
                data = f.read(CHUNK_SIZE)

            conn.sendall(data)

        conn.close()

# ------------------------------
# Register with tracker
# ------------------------------
def register_peer(file_hash, file_size, chunks, port):
    data = {
        "file_hash": file_hash,
        "file_size": file_size,
        "chunks": chunks,
        "port": port
    }
    response = requests.post(f"{TRACKER_URL}/register_peer", json=data)
    print("🔹 Register Response:", response.json())

def get_peers(file_hash):
    response = requests.get(f"{TRACKER_URL}/get_peers", params={"file_hash": file_hash})
    data = response.json()
    print(json.dumps(data, indent=4))
    return data

# ------------------------------
# MAIN
# ------------------------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--share", help="Share a file")
    args = parser.parse_args()

    if args.share:
        file_path = args.share
        port = 6000  # could randomize

        file_hash = compute_file_hash(file_path)
        file_size, chunks = split_into_chunks(file_path)

        # Start TCP server thread
        threading.Thread(target=serve_chunks, args=(port, file_path), daemon=True).start()

        # Register with tracker
        register_peer(file_hash, file_size, chunks, port)

        # Show peers
        get_peers(file_hash)

        print("✔ Peer is online & sharing")

        # Prevent exit
        threading.Event().wait()
