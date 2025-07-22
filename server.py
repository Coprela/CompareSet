import os
from typing import Dict, Any, Optional

from fastapi import FastAPI, HTTPException, Header

from github_json_manager import load_json, save_json

API_TOKEN = os.getenv("SERVER_API_TOKEN")
JSON_FILENAME = os.getenv("JSON_FILENAME", "usuarios.json")
SERVER_PORT = int(os.getenv("SERVER_PORT", "5020"))

app = FastAPI(title="CompareSet Server")


def _check_token(token: Optional[str]):
    if API_TOKEN and token != API_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid token")


@app.get("/usuarios")
def get_usuarios(x_token: Optional[str] = Header(None)):
    """Retorna o conteudo do usuarios.json."""
    _check_token(x_token)
    data = load_json(JSON_FILENAME)
    if not data:
        raise HTTPException(status_code=500, detail="Failed to load JSON")
    return data


@app.post("/usuarios")
def update_usuarios(payload: Dict[str, Any], x_token: Optional[str] = Header(None)):
    """Atualiza o usuarios.json com o conteudo fornecido."""
    _check_token(x_token)
    data = payload.get("data")
    if not isinstance(data, dict):
        raise HTTPException(status_code=400, detail="Payload must include 'data' dict")
    msg = payload.get("message", "Atualizacao via servidor")
    success = save_json(JSON_FILENAME, data, commit_message=msg)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to save JSON")
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("server:app", host="0.0.0.0", port=SERVER_PORT)
