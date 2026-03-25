import os
from fastapi import FastAPI, HTTPException

from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi import Request
from router import file_handler, csbot, sabot, ctbot, mtbot, bpbot, verificationbot
from utils.logger import setup_logging
from utils.guardrails import SecurityException
from pathlib import Path


# 判斷是否為生產環境
ENV = os.getenv("ENV", "development")  # production or development
IS_PRODUCTION = ENV == "production"

# 在生產環境中禁用 API 文件
app = FastAPI(
    docs_url=None if IS_PRODUCTION else "/docs",
    redoc_url=None if IS_PRODUCTION else "/redoc",
    openapi_url=None if IS_PRODUCTION else "/openapi.json",
)

@app.exception_handler(SecurityException)
async def security_exception_handler(request: Request, exc: SecurityException):
    return JSONResponse(
        status_code=400,
        content=exc.to_response(),
    )

# ----- Backend API ---
app.include_router(file_handler.router, prefix="/api")
app.include_router(csbot.router, prefix="/api")
app.include_router(sabot.router, prefix="/api")
app.include_router(bpbot.router, prefix="/api")
app.include_router(ctbot.router, prefix="/api")
app.include_router(mtbot.router, prefix="/api")
app.include_router(verificationbot.router, prefix="/api")


# ------ frontend router config ------
# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

# Mount static files
BASE_DIR = Path(__file__).resolve().parent
frontend_path = BASE_DIR.parent / "Frontend" / "static"
app.mount(
    "/assets", StaticFiles(directory=str(frontend_path / "assets")), name="assets"
)


#  SPA fallback
@app.get("/{full_path:path}")
async def spa_fallback(full_path: str):
    if full_path.startswith("api/"):
        raise HTTPException(status_code=404, detail="API route not found")
    index_file = frontend_path / "index.html"
    return FileResponse(index_file)


# ------ [end] frontend router config ------


setup_logging("INFO")  # 會建立 logs/app.log（JSON）


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app,
        host="127.0.0.1",
        port=5001,
        ssl_keyfile="pem_key/key.pem",
        ssl_certfile="pem_key/cert.pem",
    )
