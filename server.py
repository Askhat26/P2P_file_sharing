from flask import Flask, request, jsonify

app = Flask(__name__)

"""
TRACKER DATA STRUCTURE:

files = {
    file_hash: {
        "file_name": "testfile.txt",
        "file_size": 2048,
        "peers": [
            {
                "ip": "127.0.0.1",
                "port": 5001,
                "chunks": [0,1,2,3]
            },
            ...
        ]
    }
}
"""
files = {}


# ----------------------------------------------------
# REGISTER PEER FOR A FILE
# ----------------------------------------------------
@app.route("/register", methods=["POST"])
def register():
    data = request.json

    required = ["file_name", "file_hash", "file_size", "chunks", "ip", "port"]
    for field in required:
        if field not in data:
            return jsonify({"error": f"Missing field: {field}"}), 400

    file_hash = data["file_hash"]

    # If file hash not in registry → create new entry
    if file_hash not in files:
        files[file_hash] = {
            "file_name": data["file_name"],
            "file_size": data["file_size"],
            "peers": []
        }

    # Check for duplicate peer (same ip:port)
    peer_info = {
        "ip": data["ip"],
        "port": data["port"],
        "chunks": data["chunks"]
    }

    existing_peer = next(
        (p for p in files[file_hash]["peers"] 
         if p["ip"] == peer_info["ip"] and p["port"] == peer_info["port"]), 
        None
    )

    if existing_peer:
        # Update existing peer's chunks
        existing_peer["chunks"] = peer_info["chunks"]
        message = "Peer updated successfully"
    else:
        # Add new peer
        files[file_hash]["peers"].append(peer_info)
        message = "Peer registered successfully"

    return jsonify({
        "message": message,
        "file_hash": file_hash,
        "peers_count": len(files[file_hash]["peers"])
    }), 200


# ----------------------------------------------------
# LOOKUP FILE BY NAME (FIXED ENDPOINT)
# ----------------------------------------------------
@app.route("/lookup", methods=["GET"])
def lookup():
    filename = request.args.get("file_name")
    
    if not filename:
        return jsonify({"error": "Missing file_name parameter"}), 400

    # Find file entry by filename
    for file_hash, info in files.items():
        if info["file_name"] == filename:
            return jsonify({
                "file_hash": file_hash,
                "file_name": info["file_name"],
                "file_size": info["file_size"],
                "peers": info["peers"]
            }), 200

    return jsonify({"error": "File not found"}), 404


# ----------------------------------------------------
# GET FILE INFO BY NAME (LEGACY ENDPOINT - OPTIONAL)
# ----------------------------------------------------
@app.route("/get_file/<filename>", methods=["GET"])
def get_file(filename):
    # Find file entry by filename
    for file_hash, info in files.items():
        if info["file_name"] == filename:
            return jsonify({
                "file_hash": file_hash,
                "file_name": info["file_name"],
                "file_size": info["file_size"],
                "peers": info["peers"]
            }), 200

    return jsonify({"error": "File not found"}), 404


# ----------------------------------------------------
# LIST ALL FILES (OPTIONAL - FOR DEBUGGING)
# ----------------------------------------------------
@app.route("/files", methods=["GET"])
def list_files():
    file_list = []
    for file_hash, info in files.items():
        file_list.append({
            "file_hash": file_hash,
            "file_name": info["file_name"],
            "file_size": info["file_size"],
            "peers_count": len(info["peers"])
        })
    return jsonify({"files": file_list}), 200


# ----------------------------------------------------
# RUN SERVER
# ----------------------------------------------------
if __name__ == "__main__":
    print("📡 Tracker server running on http://127.0.0.1:5000")
    print("📋 Endpoints:")
    print("   POST   /register - Register a peer")
    print("   GET    /lookup?file_name=<name> - Find peers for a file")
    print("   GET    /files - List all tracked files")
    app.run(host="0.0.0.0", port=5000, debug=True)