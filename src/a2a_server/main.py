from fastapi import FastAPI

app = FastAPI(title="OSSS A2A Server")

@app.get("/health")
async def health():
    return {"status": "ok"}

@app.get("/")
async def root():
    return {"message": "A2A server is alive"}
