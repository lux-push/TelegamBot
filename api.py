from api import FastAPI
from config import API_PORT
from db import Database

app = FastAPI()
db = Database()

@app.get("/health")
async def health_check():
    return {"status": "OK", "bots": "running"}

@app.get("/ads/avito")
async def get_avito_ads():
    ads = db.get_new_ads("avito_ads", 10)
    return {"ads": ads}

if __name__ == "__main__":
    import uvicorn # type: ignore
    uvicorn.run(app, host="0.0.0.0", port=API_PORT)