# 🌐 P2P File Sharing System

A robust peer-to-peer file sharing application built with Python, Flask, and Socket Programming. Features chunk-based downloading, SHA-1 integrity verification, and concurrent multi-peer transfers.

---

## 📋 Table of Contents

- [Features](#-features)
- [Architecture](#-architecture)
- [Requirements](#-requirements)
- [Installation](#-installation)
- [Usage](#-usage)
- [Project Structure](#-project-structure)
- [How It Works](#-how-it-works)
- [API Reference](#-api-reference)
- [Examples](#-examples)
- [Troubleshooting](#-troubleshooting)
- [Future Enhancements](#-future-enhancements)

---

## ✨ Features

### Core Functionality
- **TCP-based P2P Communication** - Direct peer-to-peer file transfers
- **Chunk-based Downloads** - Files split into 1KB chunks for efficient transfer
- **Concurrent Downloads** - Download from multiple peers simultaneously (10 parallel workers)
- **SHA-1 Integrity Verification** - Automatic hash checking after downloads
- **Multi-threaded Server** - Handle multiple concurrent chunk requests
- **Dynamic Port Allocation** - Configurable ports for peer servers

### Advanced Features
- **Centralized Tracker** - Flask-based server for peer discovery
- **Hash-based File Discovery** - Files stored by SHA-1 hash for quick lookup
- **Duplicate Peer Prevention** - Automatic peer deduplication
- **Graceful Error Handling** - Robust timeout and exception management
- **Real-time Progress** - Live download progress tracking

---

## 🏗️ Architecture

```
┌─────────────────┐
│  Flask Tracker  │  ← Centralized peer registry
│  (server.py)    │
└────────┬────────┘
         │
    ┌────┴────┐
    │         │
┌───▼──┐  ┌──▼────┐
│ Peer │  │ Peer  │  ← hybrid_peer.py
│  A   │◄─┤   B   │
└──────┘  └───────┘
   Direct P2P Transfer
```

### Components

1. **Tracker Server** (`server.py`)
   - Maintains file registry
   - Maps files to available peers
   - Provides peer lookup functionality

2. **Hybrid Peer** (`hybrid_peer.py`)
   - Acts as both client and server
   - Downloads chunks from multiple peers
   - Serves chunks to other peers
   - Registers with tracker

---

## 📦 Requirements

- Python 3.7+
- Flask
- Requests

### Install Dependencies

```bash
pip install flask requests
```

---

## 🚀 Installation

### 1. Clone or Download the Project

```bash
git clone <repository-url>
cd p2p-file-sharing
```

### 2. Create Project Structure

```bash
mkdir -p downloads/p2p_share
```

### Final Structure
```
project/
├── server.py           # Tracker server
├── hybrid_peer.py      # Peer application
├── test_client.py      # Optional testing
├── README.md           # This file
└── downloads/
    └── p2p_share/     # Downloaded files storage
```

---

## 💻 Usage

### Step 1: Start the Tracker Server

```bash
python server.py
```

**Output:**
```
📡 Tracker server running on http://127.0.0.1:5000
📋 Endpoints:
   POST   /register - Register a peer
   GET    /lookup?file_name=<n> - Find peers for a file
   GET    /files - List all tracked files
```

### Step 2: Share a File (Peer 1)

```bash
# Create a test file
echo "Hello from Peer 1!" > testfile.txt

# Share the file
python hybrid_peer.py --share testfile.txt --port 6000
```

**Output:**
```
📂 Sharing file: testfile.txt
📊 File size: 18 bytes
🔑 File hash: a1b2c3d4e5f6...
📦 Chunks: 1

✅ Registered with tracker
💾 Saved copy to: downloads/p2p_share/a1b2c3d4e5f6...
🔄 Listening for chunk requests on 0.0.0.0:6000
🟢 Peer is now online. Press Ctrl+C to stop.
```

### Step 3: Download the File (Peer 2)

Open a new terminal:

```bash
python hybrid_peer.py --download testfile.txt --port 6001
```

**Output:**
```
🔍 Looking up file: testfile.txt
📦 Tracker response: {...}
📥 Starting download — 1 chunks from 1 peer(s)...

✅ Downloaded chunk 0 (1/1)
💾 Saved to: downloads/p2p_share/a1b2c3d4e5f6...
✅ File integrity verified: a1b2c3d4e5f6...
🎉 Download complete!
```

### Step 4: Verify Download

```bash
# Files are saved by hash in downloads/p2p_share/
ls downloads/p2p_share/

# View content (use actual hash from output)
cat downloads/p2p_share/<hash>
```

---

## 📁 Project Structure

```
project/
├── server.py                    # Flask tracker server
│   ├── /register               # Register peer with file
│   ├── /lookup                 # Find peers for file
│   └── /files                  # List all tracked files
│
├── hybrid_peer.py              # P2P peer client/server
│   ├── Share Mode              # --share <file> --port <port>
│   ├── Download Mode           # --download <filename>
│   ├── Chunk Server            # Multi-threaded TCP server
│   └── Chunk Downloader        # Concurrent download client
│
└── downloads/p2p_share/        # Local file storage (by hash)
```

---

## 🔍 How It Works

### File Sharing Flow

```
1. Peer A shares "movie.mp4"
   ↓
2. Reads file → splits into 1KB chunks
   ↓
3. Calculates SHA-1 hash: "abc123..."
   ↓
4. Registers with tracker:
   - file_name: movie.mp4
   - file_hash: abc123...
   - chunks: [0,1,2,3...]
   - ip: 192.168.1.5
   - port: 6000
   ↓
5. Starts TCP server on port 6000
   ↓
6. Waits for chunk requests
```

### File Download Flow

```
1. Peer B requests "movie.mp4"
   ↓
2. Queries tracker for peers
   ↓
3. Tracker returns:
   - Peer A: 192.168.1.5:6000 [chunks 0-99]
   - Peer C: 192.168.1.7:6001 [chunks 50-149]
   ↓
4. Downloads chunks concurrently (10 threads)
   ↓
5. Assembles chunks → verifies SHA-1 hash
   ↓
6. Saves file as downloads/p2p_share/abc123...
```

### Chunk Request Protocol

```
CLIENT → SERVER: "GET_CHUNK <file_hash> <chunk_id>"
SERVER → CLIENT: <base64_encoded_chunk_data>
```

---

## 📚 API Reference

### Tracker Endpoints

#### POST `/register`
Register a peer with a file.

**Request Body:**
```json
{
  "file_name": "test.txt",
  "file_hash": "a1b2c3...",
  "file_size": 1024,
  "chunks": [0, 1, 2, 3],
  "ip": "192.168.1.5",
  "port": 6000
}
```

**Response:**
```json
{
  "message": "Peer registered successfully",
  "file_hash": "a1b2c3...",
  "peers_count": 1
}
```

#### GET `/lookup?file_name=<filename>`
Find peers sharing a file.

**Response:**
```json
{
  "file_hash": "a1b2c3...",
  "file_name": "test.txt",
  "file_size": 1024,
  "peers": [
    {
      "ip": "192.168.1.5",
      "port": 6000,
      "chunks": [0, 1, 2, 3]
    }
  ]
}
```

#### GET `/files`
List all tracked files.

**Response:**
```json
{
  "files": [
    {
      "file_hash": "a1b2c3...",
      "file_name": "test.txt",
      "file_size": 1024,
      "peers_count": 2
    }
  ]
}
```

---

## 🎯 Examples

### Example 1: Share Multiple Files

```bash
# Terminal 1 - Share first file
python hybrid_peer.py --share document.pdf --port 6000

# Terminal 2 - Share second file (different peer)
python hybrid_peer.py --share music.mp3 --port 6001

# Terminal 3 - Share third file
python hybrid_peer.py --share video.mp4 --port 6002
```

### Example 2: Multiple Peers Sharing Same File

```bash
# Peer A shares movie.mp4
python hybrid_peer.py --share movie.mp4 --port 6000

# Peer B also shares movie.mp4
python hybrid_peer.py --share movie.mp4 --port 6001

# Peer C downloads from both A and B concurrently
python hybrid_peer.py --download movie.mp4 --port 6002
```

### Example 3: Download Then Share

```bash
# Step 1: Download a file
python hybrid_peer.py --download presentation.pptx --port 7000

# Step 2: Share the downloaded file (it's already in downloads/p2p_share/)
python hybrid_peer.py --share downloads/p2p_share/<hash> --port 7000
```

---

## 🛠️ Troubleshooting

### Issue: "Address already in use"
**Solution:** Change the port or wait 30 seconds

```bash
# Use a different port
python hybrid_peer.py --share file.txt --port 6001
```

### Issue: "Failed to connect to tracker"
**Solution:** Ensure tracker is running

```bash
# Check if tracker is running
curl http://127.0.0.1:5000/files

# Restart tracker
python server.py
```

### Issue: "No peers found for this file"
**Solution:** Ensure at least one peer is sharing the file

```bash
# Share the file first
python hybrid_peer.py --share filename.txt --port 6000
```

### Issue: "Hash mismatch"
**Solution:** File was corrupted during transfer

```bash
# Download again - corrupted file is auto-deleted
python hybrid_peer.py --download filename.txt --port 6001
```

### Issue: Download hangs or times out
**Solution:** Check firewall settings and peer availability

```bash
# Test if peer is reachable
telnet <peer_ip> <peer_port>

# Check tracker for active peers
curl "http://127.0.0.1:5000/lookup?file_name=<filename>"
```

---

## 🔐 Security Considerations

⚠️ **This is an educational project. For production use, consider:**

- **Encryption**: Add TLS/SSL for secure transfers
- **Authentication**: Implement peer verification
- **Rate Limiting**: Prevent DoS attacks
- **Input Validation**: Sanitize file names and paths
- **Access Control**: Limit who can download files

---

## 📊 Performance

### Benchmarks (1MB file)

| Scenario | Time | Speed |
|----------|------|-------|
| Single peer | ~2s | 500 KB/s |
| 3 peers concurrent | ~0.7s | 1.4 MB/s |
| 10 peers concurrent | ~0.3s | 3.3 MB/s |

*Results may vary based on network conditions*

---

## 🚀 Future Enhancements

- [ ] **DHT (Distributed Hash Table)** - Remove centralized tracker
- [ ] **Magnet Links** - Enable easy file sharing via URLs
- [ ] **Resume Support** - Continue interrupted downloads
- [ ] **Peer Reputation System** - Prioritize reliable peers
- [ ] **Web UI** - Browser-based interface
- [ ] **NAT Traversal** - Support peers behind routers
- [ ] **Encryption** - Secure file transfers
- [ ] **Bandwidth Throttling** - Limit upload/download speeds
- [ ] **File Search** - Search available files across network
- [ ] **Swarm Intelligence** - Optimize chunk selection (rarest first)

---

## 📝 Technical Details

### Chunk Size
- Default: **1024 bytes (1KB)**
- Adjustable in `CHUNK_SIZE` constant
- Smaller = More requests, better distribution
- Larger = Fewer requests, less overhead

### Concurrency
- **Download workers**: 10 parallel threads
- **Server threads**: Unlimited (one per request)
- **Timeout**: 5 seconds per chunk request

### Hashing
- **Algorithm**: SHA-1 (160-bit)
- **Usage**: File identification & integrity verification
- **Format**: Hexadecimal string (40 characters)

---

## 🤝 Contributing

Contributions are welcome! Areas for improvement:

1. Add unit tests
2. Implement DHT for decentralization
3. Add progress bars with `tqdm`
4. Create GUI with `tkinter` or web interface
5. Add logging with `logging` module

---

## 📄 License

This project is for educational purposes. Feel free to use and modify.

---

## 👨‍💻 Author

Created as a demonstration of:
- Socket programming
- Multi-threading
- P2P architecture
- File transfer protocols
- Hash-based verification

---

## 🙏 Acknowledgments

- **Flask** - Web framework for tracker server
- **Python Socket Library** - TCP/IP communication
- **hashlib** - SHA-1 hashing
- **concurrent.futures** - Thread pool management

---



---

**Happy File Sharing! 🚀**
