from flask import Flask, jsonify
import subprocess, os

app = Flask(__name__)

@app.get("/health")
def health():
    try:
        # Cheap sanity check that dvc is callable
        subprocess.run(["dvc","--version"], check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return jsonify(status="ok")
    except Exception as e:
        return jsonify(status="error", detail=type(e).__name__), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("HEALTH_PORT", 8010)))
