import json
import time
from pathlib import Path
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.memory import MemorySaver
from fastapi import APIRouter
from fastapi.responses import JSONResponse

from graph.verification_graph import VerificationGraph
from state.state import VerificationState
from utils.api_parser import RuleData
from utils.llm import get_llm_client
from utils.paths import USER_DIR
from utils.tools import write_user_info
from utils.auth_token import verify_token, decrypt_aes_gcm

router = APIRouter(
    prefix="/vf",
    tags=["Verification Bot"],
)


@router.post("/regenerate")
def regenerate_code(data: RuleData):
    """
    {
        "uuid":"12345",
        "token":"token_string",
        "expire_time": "2025-11-26T12:09:14.139012",
        "project_info": "",
        "language": "Delphi",
        "model":"OpenAI",
        "api_key": "key",
        "model_name": "gpt-oss:120b",
        "base_url": "http://127.0.0.1:8000"
    }

    Handles a POST request to regenerate the code based on previous errors.
    Uses VerificationGraph to perform the fix.
    """
    # --- 1. Initialization ---
    verify_token(data.uuid, data.token, expire_time=data.expire_time)

    user_path = Path(USER_DIR, data.uuid)
    with open(user_path, "r", encoding="utf-8") as f:
        user_info = json.load(f)

    # --- 2. AI Model Setup ---
    try:
        llm = get_llm_client(
            model=data.model,
            api_key=decrypt_aes_gcm(data.api_key),
            model_name=data.model_name,
            base_url=data.base_url,
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "error_code": "500",
                "message": f"Failed to load llm model: {e}",
            },
        )

    # --- 3. Graph Execution ---
    memory = MemorySaver()
    verification_graph = VerificationGraph()
    config: RunnableConfig = {"configurable": {"thread_id": data.uuid, "model": llm}}
    verification_app = verification_graph.compile(memory)

    input_state: VerificationState = {
        "uuid": data.uuid,
        "developers_output_path": user_info.get("developers_output_path", ""),
        "blueprint_json_path": user_info.get(
            "blueprint_json_path_updated", user_info.get("blueprint_json_path", "")
        ),
        "verification_sensitive": ["name", "description", "input", "output"],
    }

    result = verification_app.invoke(
        input=input_state,
        config=config,
    )

    # Persist updated info (e.g., verification outputs)
    user_info["developers_output_path"] = result.get(
        "developers_output_path", user_info.get("developers_output_path", "")
    )
    user_info["fixed_code_path"] = result.get("fixed_code_path", "")
    write_user_info(user_info=user_info, file_path=str(user_path))

    # Load release note content; message must be the release note
    release_note_text = ""
    try:
        release_note_path = (
            Path(user_info.get("developers_output_path", "")) / "release_note.md"
        )
        if release_note_path.exists():
            with open(release_note_path, "r", encoding="utf-8") as f:
                release_note_text = f.read().strip()
    except Exception:
        release_note_text = ""

    if not release_note_text:
        release_note_text = (
            "Verification completed, but release_note.md was not found or empty."
        )

    return JSONResponse(
        status_code=200,
        content={
            "status": "success",
            "uuid": data.uuid,
            "message": release_note_text,
        },
    )
