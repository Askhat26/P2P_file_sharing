import requests
import socket
import argparse
import threading
import hashlib
import os
import time
import random
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed

TRACKER_URL = "http://127.0.0.1:5000"
CHUNK_SIZE = 1024 * 1024  # 1MB chunks (optimal for modern networks)


###############################################################
# Utility
###############################################################

def sha1_hash(data: bytes):
    return hashlib.sha1(data).hexdigest()


def get_file_info(file_path):
    """Get file size and hash without loading entire file into memory."""
    file_size = os.path.getsize(file_path)
    
    # Calculate hash in chunks to handle large files
    sha1 = hashlib.sha1()
    with open(file_path, "rb") as f:
        while True:
            chunk = f.read(CHUNK_SIZE)
            if not chunk:
                break
            sha1.update(chunk)
    
    file_hash = sha1.hexdigest()
    num_chunks = (file_size + CHUNK_SIZE - 1) // CHUNK_SIZE
    
    return file_hash, file_size, num_chunks


def get_local_ip():
    """Return LAN IP instead of 0.0.0.0."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except (OSError, socket.error) as e:
        print(f"⚠️  Warning: Could not detect IP: {e}")
        return "127.0.0.1"
    finally:
        s.close()


###############################################################
# Tracker communication
###############################################################

def register_with_tracker(file_name, file_hash, file_size, port, num_chunks, ip):
    payload = {
        "file_name": file_name,
        "file_hash": file_hash,
        "file_size": file_size,
        "chunks": list(range(num_chunks)),  # All chunks available
        "ip": ip,
        "port": port
    }

    print("📤 Registering with tracker...\n", payload)
    try:
        res = requests.post(f"{TRACKER_URL}/register", json=payload, timeout=5)
        
        if res.status_code != 200:
            raise Exception(f"Tracker registration failed: {res.text}")
        
        return res.json()
    except requests.exceptions.RequestException as e:
        raise Exception(f"Failed to connect to tracker: {e}")


def lookup_peers(file_name):
    try:
        r = requests.get(f"{TRACKER_URL}/lookup", params={"file_name": file_name}, timeout=5)
        if r.status_code != 200:
            print(f"❌ Tracker error: {r.json().get('error', 'Unknown error')}")
            return {}
        return r.json()
    except requests.exceptions.RequestException as e:
        print(f"❌ Failed to connect to tracker: {e}")
        return {}


###############################################################
# Chunk Server (Memory-Efficient with Lazy Loading)
###############################################################

def handle_peer_connection(conn, addr, hosted_files):
    """
    Handle individual chunk request with lazy loading.
    Only reads the requested chunk from disk, not the entire file.
    """
    try:
        # Receive request
        req = conn.recv(1024).decode().strip().split()

        if len(req) != 3 or req[0] != "GET_CHUNK":
            print(f"⚠️  Invalid request from {addr}: {req}")
            return

        file_hash = req[1]
        chunk_id = int(req[2])

        if file_hash not in hosted_files:
            print(f"⚠️  File hash {file_hash} not found")
            conn.sendall(b"ERROR: File not found")
            return

        file_path = hosted_files[file_hash]
        file_size = os.path.getsize(file_path)
        num_chunks = (file_size + CHUNK_SIZE - 1) // CHUNK_SIZE

        if chunk_id >= num_chunks:
            print(f"⚠️  Chunk {chunk_id} out of range (max: {num_chunks-1})")
            conn.sendall(b"ERROR: Chunk out of range")
            return

        # Calculate offset and read only the requested chunk
        offset = chunk_id * CHUNK_SIZE
        
        with open(file_path, "rb") as f:
            f.seek(offset)
            chunk_data = f.read(CHUNK_SIZE)

        # Send chunk size first (4 bytes), then raw chunk data
        chunk_size_bytes = len(chunk_data).to_bytes(4, byteorder='big')
        conn.sendall(chunk_size_bytes)
        conn.sendall(chunk_data)
        
        print(f"✅ Sent chunk {chunk_id} ({len(chunk_data)} bytes) to {addr[0]}:{addr[1]}")

    except Exception as e:
        print(f"❌ Error handling request from {addr}: {e}")
        try:
            conn.sendall(b"ERROR: Server error")
        except:
            pass
    finally:
        conn.close()


def chunk_server(port, hosted_files):
    """Multi-threaded chunk server with lazy loading."""
    server_ip = "0.0.0.0"
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    
    try:
        s.bind((server_ip, port))
        s.listen(10)  # Increased backlog for more concurrent connections
        print(f"🔄 Listening for chunk requests on {server_ip}:{port}")
    except OSError as e:
        print(f"❌ Failed to bind to port {port}: {e}")
        return

    while True:
        try:
            conn, addr = s.accept()
            # Handle each request in a separate thread
            threading.Thread(
                target=handle_peer_connection,
                args=(conn, addr, hosted_files),
                daemon=True
            ).start()
        except KeyboardInterrupt:
            print("\n🛑 Shutting down chunk server...")
            break
        except Exception as e:
            print(f"❌ Server error: {e}")


###############################################################
# Chunk Downloader (Raw Bytes, No Base64)
###############################################################

def download_chunk(ip, port, file_hash, chunk_id):
    """Download a single chunk from a peer using raw bytes."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(10)  # Increased timeout for 1MB chunks
        s.connect((ip, port))
        
        # Send request
        req = f"GET_CHUNK {file_hash} {chunk_id}".encode()
        s.sendall(req)

        # First, receive the chunk size (4 bytes)
        size_bytes = s.recv(4)
        if len(size_bytes) < 4:
            return None
        
        chunk_size = int.from_bytes(size_bytes, byteorder='big')
        
        # Now receive the actual chunk data
        data = b""
        remaining = chunk_size
        
        while remaining > 0:
            chunk = s.recv(min(remaining, 65536))  # 64KB buffer
            if not chunk:
                break
            data += chunk
            remaining -= len(chunk)
        
        s.close()
        
        if len(data) != chunk_size:
            print(f"   ⚠️  Incomplete chunk: expected {chunk_size}, got {len(data)}")
            return None
        
        return data

    except socket.timeout:
        print(f"   ⏱️  Timeout connecting to {ip}:{port}")
        return None
    except Exception as e:
        print(f"   ❌ Error downloading from {ip}:{port}: {e}")
        return None


def download_chunk_wrapper(peer_ip, peer_port, file_hash, chunk_id):
    """Wrapper for concurrent download."""
    data = download_chunk(peer_ip, peer_port, file_hash, chunk_id)
    return chunk_id, data


###############################################################
# Load Balancing Logic
###############################################################

def build_chunk_availability_map(peers, num_chunks):
    """
    Build a map of which peers have which chunks.
    Returns: dict {chunk_id: [list of peers]}
    """
    chunk_availability = defaultdict(list)
    
    for peer in peers:
        peer_info = {
            "ip": peer["ip"],
            "port": peer["port"]
        }
        for chunk_id in peer["chunks"]:
            if chunk_id < num_chunks:
                chunk_availability[chunk_id].append(peer_info)
    
    return chunk_availability


def create_download_plan(chunk_availability, num_chunks):
    """
    Create an optimal download plan by assigning each chunk to ONE random peer.
    This ensures load balancing and prevents duplicate downloads.
    
    Returns: list of (peer_ip, peer_port, chunk_id) tuples
    """
    download_tasks = []
    
    for chunk_id in range(num_chunks):
        available_peers = chunk_availability.get(chunk_id, [])
        
        if not available_peers:
            print(f"⚠️  Warning: No peers available for chunk {chunk_id}")
            continue
        
        # Pick a random peer for load balancing
        selected_peer = random.choice(available_peers)
        download_tasks.append((selected_peer["ip"], selected_peer["port"], chunk_id))
    
    return download_tasks


###############################################################
# Main Peer Logic
###############################################################

def main():
    parser = argparse.ArgumentParser(description="P2P File Sharing Hybrid Peer (Optimized)")
    parser.add_argument("--share", help="Share a file (provide file path)")
    parser.add_argument("--download", help="Download a file (provide file name)")
    parser.add_argument("--port", type=int, default=6000, help="Port for chunk server (default: 6000)")
    args = parser.parse_args()

    hosted_files = {}  # {file_hash: file_path} - Memory efficient!
    local_ip = get_local_ip()

    ###############################################################
    # SHARE MODE (Memory-Efficient)
    ###############################################################
    if args.share:
        if not os.path.exists(args.share):
            print("❌ File not found:", args.share)
            return

        print(f"\n📂 Sharing file: {args.share}")
        
        # Get file info without loading into memory
        file_hash, file_size, num_chunks = get_file_info(args.share)

        print(f"📊 File size: {file_size:,} bytes ({file_size / (1024**2):.2f} MB)")
        print(f"🔑 File hash: {file_hash}")
        print(f"📦 Chunks: {num_chunks} x {CHUNK_SIZE / (1024**2):.2f} MB\n")

        # Register with tracker
        try:
            res = register_with_tracker(
                file_name=os.path.basename(args.share),
                file_hash=file_hash,
                file_size=file_size,
                port=args.port,
                num_chunks=num_chunks,
                ip=local_ip
            )
            print(f"✅ Registered with tracker: {res}\n")
        except Exception as e:
            print(f"❌ Registration failed: {e}")
            return

        # Store only the file path (not the chunks!)
        hosted_files[file_hash] = os.path.abspath(args.share)

        # Save a copy in downloads/p2p_share/ for discovery (optional)
        download_dir = "downloads/p2p_share"
        os.makedirs(download_dir, exist_ok=True)
        copy_path = os.path.join(download_dir, file_hash)
        
        # Only copy if not already there
        if not os.path.exists(copy_path):
            import shutil
            shutil.copy2(args.share, copy_path)
            print(f"💾 Saved copy to: {copy_path}\n")
        else:
            print(f"💾 Copy already exists: {copy_path}\n")

        # Start chunk server in background
        threading.Thread(
            target=chunk_server,
            args=(args.port, hosted_files),
            daemon=True
        ).start()

        # Keep peer alive
        print("🟢 Peer is now online. Press Ctrl+C to stop.\n")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n👋 Shutting down peer...")

    ###############################################################
    # DOWNLOAD MODE (Load Balanced)
    ###############################################################
    elif args.download:
        print(f"\n🔍 Looking up file: {args.download}\n")
        meta = lookup_peers(args.download)

        if not meta:
            print("❌ Failed to get file information from tracker.")
            return

        print("📦 Tracker response:\n", meta, "\n")

        peers = meta.get("peers", [])
        file_size = meta.get("file_size", 0)
        file_hash = meta.get("file_hash", "")

        if not peers:
            print("❌ No peers found for this file.")
            return

        if not file_hash:
            print("❌ File hash not provided by tracker.")
            return

        num_chunks = (file_size + CHUNK_SIZE - 1) // CHUNK_SIZE
        output_chunks = [None] * num_chunks

        print(f"📥 Starting download — {num_chunks} chunks from {len(peers)} peer(s)...\n")

        # Build chunk availability map
        chunk_availability = build_chunk_availability_map(peers, num_chunks)
        
        # Create optimized download plan (one peer per chunk)
        download_tasks = create_download_plan(chunk_availability, num_chunks)
        
        print(f"🎯 Download plan: {len(download_tasks)} tasks across {len(peers)} peers\n")

        # Download chunks concurrently with load balancing
        successful_downloads = 0
        failed_chunks = []
        
        with ThreadPoolExecutor(max_workers=10) as executor:
            future_to_chunk = {
                executor.submit(download_chunk_wrapper, ip, port, file_hash, cid): cid
                for ip, port, cid in download_tasks
            }

            for future in as_completed(future_to_chunk):
                chunk_id, data = future.result()
                if data and output_chunks[chunk_id] is None:
                    output_chunks[chunk_id] = data
                    successful_downloads += 1
                    print(f"✅ Downloaded chunk {chunk_id} ({len(data):,} bytes) - Progress: {successful_downloads}/{num_chunks}")
                else:
                    failed_chunks.append(chunk_id)

        # Retry failed chunks
        if failed_chunks:
            print(f"\n⚠️  Retrying {len(failed_chunks)} failed chunks...")
            for chunk_id in failed_chunks:
                available_peers = chunk_availability.get(chunk_id, [])
                for peer in available_peers:
                    data = download_chunk(peer["ip"], peer["port"], file_hash, chunk_id)
                    if data:
                        output_chunks[chunk_id] = data
                        successful_downloads += 1
                        print(f"✅ Retry successful: chunk {chunk_id}")
                        break

        # Check for missing chunks
        if None in output_chunks:
            missing = [i for i, c in enumerate(output_chunks) if c is None]
            print(f"\n❌ Download incomplete — missing chunks: {missing}")
            return

        # Save downloaded file
        download_dir = "downloads/p2p_share"
        os.makedirs(download_dir, exist_ok=True)
        output_file = os.path.join(download_dir, file_hash)

        print(f"\n💾 Writing file to disk...")
        with open(output_file, "wb") as f:
            for c in output_chunks:
                f.write(c)

        print(f"💾 Saved to: {output_file}")

        # Verify file integrity
        print(f"🔍 Verifying file integrity...")
        with open(output_file, "rb") as f:
            sha1 = hashlib.sha1()
            while True:
                chunk = f.read(CHUNK_SIZE)
                if not chunk:
                    break
                sha1.update(chunk)
            downloaded_hash = sha1.hexdigest()

        if downloaded_hash != file_hash:
            print(f"❌ Hash mismatch! Expected {file_hash}, got {downloaded_hash}")
            os.remove(output_file)
            print(f"🗑️  Removed corrupted file.")
        else:
            print(f"✅ File integrity verified: {downloaded_hash}")
            print(f"\n🎉 Download complete! File saved as: {output_file}")
            print(f"📊 Total size: {file_size:,} bytes ({file_size / (1024**2):.2f} MB)")

    else:
        print("❌ Please specify --share or --download")
        parser.print_help()


if __name__ == "__main__":
    main()