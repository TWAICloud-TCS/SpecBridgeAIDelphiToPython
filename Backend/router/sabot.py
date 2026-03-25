import os
import json
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.memory import MemorySaver
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pathlib import Path

from state.state import SAState
from graph.sa_graph import SAGraph
from utils.api_parser import RuleData
from utils.llm import get_llm_client
from utils.tools import write_user_info
from utils.paths import get_output_doc_dir, USER_DIR, ensure_uuid_directories
from utils.auth_token import verify_token, decrypt_aes_gcm
from utils.encryption import decrypt_sensitive_data

router = APIRouter(
    prefix="/sa",
    tags=["LangGraph System Analyst Generator"],
)


@router.post("/document")
async def sa_doc(data: RuleData):
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

    Generate a System Analysis (SA) document using LangGraph workflow.

    1. Parse UUID from the request payload.
    2. Load user-specific configuration from 'users/{uuid}'.
    3. Execute the SA Graph workflow to generate the document.
    4. Save the SA document to 'output_doc/{uuid}_sa.json'.
    5. Update user metadata with the SA document path.

    Args:
        data (RuleData): Request body containing 'data' dict.

    Returns:
        dict: SA document generation results and file paths.
    """

    verify_token(data.uuid, data.token, expire_time=data.expire_time)

    try:
        # Construct the path to the user's information file using the UUID.
        user_path = Path(USER_DIR, data.uuid)
        # Read and load the user information.
        with open(user_path, "r", encoding="utf-8") as f:
            user_info = json.load(f)
    except Exception as e:
        # Return a standardized 500 error if reading the user file fails.
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "error_code": "500",
                "message": f"Failed to get user file: {e}",
            },
        )

    # Ensure UUID directories exist
    ensure_uuid_directories(data.uuid)

    # Construct the full path for the output SA document.
    output_doc_dir = get_output_doc_dir(data.uuid)
    output_sa_path = os.path.join(os.getcwd(), str(output_doc_dir), "sa.json")

    source_path = user_info.get("source_path", "")
    if not Path(source_path).is_absolute():
        source_path = str(Path.cwd() / source_path)

    try:
        llm = get_llm_client(
            model=data.model,
            api_key=decrypt_aes_gcm(data.api_key),
            model_name=data.model_name,
            base_url=data.base_url,
        )
    except Exception as e:
        # Return a standardized 500 error if the model fails to load.
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "error_code": "500",
                "message": f"Failed to load llm model: {e}",
            },
        )

    # Initialize LangGraph's memory saver for persisting state.
    memory = MemorySaver()
    # Create a new instance of the SAGraph.
    sa_graph = SAGraph()

    # Configure the execution parameters for LangGraph, including the thread ID and LLM model.
    config: RunnableConfig = {"configurable": {"thread_id": data.uuid, "model": llm}}
    # Compile the graph with memory to make it an executable application.
    sa_app = sa_graph.compile(memory)
    # Invoke the graph, passing the UUID and project name as input.

    input_state: SAState = {
        "uuid": data.uuid,
        "cs_original_path": user_info.get("cs_json_path", ""),
        "cs_json_path": user_info.get("cs_json_path_updated", ""),
        "project_name": user_info.get("project_name", ""),
        "source_path": source_path,
        "project_info": data.project_info,
        "sa_sensitive": ["title", "content"],
    }

    _ = sa_app.invoke(
        input=input_state,
        config=config,
    )

    # Update the user information with the path to the generated SA document.
    user_info["sa_txt_path"] = str(output_sa_path)
    # Write the updated user information back to the file.
    write_user_info(user_info=user_info, file_path=str(user_path))

    # Read the generated SA data to include in the response.
    try:
        with open(output_sa_path, "r", encoding="utf-8") as f:
            sa_data = json.load(f)

        sa_data = decrypt_sensitive_data(sa_data, sensitive_fields=["title", "content"])
        # Return a success response containing the UUID and the SA document content.
        return {"uuid": data.uuid, "doc_sa": sa_data}

    except Exception as e:
        # Return a standardized 500 error if reading the generated SA file fails.
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "error_code": "500",
                "message": f"Failed to load sa file: {e}",
            },
        )
