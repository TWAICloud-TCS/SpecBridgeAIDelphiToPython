import os
import json
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.memory import MemorySaver
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pathlib import Path

from graph.cs_graph import CSGraph
from state.state import CSState
from utils.api_parser import RuleData
from utils.llm import get_llm_client
from utils.tools import write_user_info
from utils.paths import get_output_doc_dir, USER_DIR, ensure_uuid_directories
from utils.auth_token import verify_token, decrypt_aes_gcm
from utils.encryption import decrypt_sensitive_data

router = APIRouter(
    prefix="/cs",
    tags=["Code structure Generator"],
)


@router.post("/document")
async def code_doc(data: RuleData):
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

    Process source files to generate an intermediary JSON document via LLM.

    LLM Fallback Strategy:
    1. Primary: Ollama GPT OSS Client (recommended method)
    2. Secondary: GPTOSSLLM (if Ollama client fails)
    3. Tertiary: OpenAI API (if both GPT OSS methods fail)

    1. Parse UUID and API key from the request payload.
    2. Load user-specific configuration from 'users/{uuid}'.
    3. Execute CS workflow which includes preprocess analysis to generate file_dependency_lists.
    4. Generate intermediary document based on file dependency groups.
    5. Format and save all LLM responses to 'output_doc/{uuid}_intermediary_document.json'.
    6. Update user metadata with new paths and API key.

    Args:
        data (RuleData): Request body containing 'data' dict.

    Returns:
        dict: Response containing paths to generated documents.
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

    # Define output paths for the generated JSON and CSV documents.
    output_doc_dir = get_output_doc_dir(data.uuid)
    cs_json_path = os.path.join(os.getcwd(), str(output_doc_dir), "cs_document.json")
    cs_csv_path = os.path.join(os.getcwd(), str(output_doc_dir), "cs_document.csv")
    json_language_analysis_path = os.path.join(
        os.getcwd(), str(output_doc_dir), "preprocess_analysis.json"
    )

    # Update user metadata with paths
    user_info["cs_json_path"] = str(cs_json_path)
    user_info["cs_csv_path"] = str(cs_csv_path)

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
                "message": f"Failed to load LLM model: {e}",
            },
        )

    # Initialize LangGraph's memory saver for persisting state.
    memory = MemorySaver()
    # Create a new instance of the CSGraph.
    cs_graph = CSGraph()

    # Configure the execution parameters for LangGraph, including the thread ID and LLM model.
    config: RunnableConfig = {"configurable": {"thread_id": data.uuid, "model": llm}}
    # Compile the graph with memory to make it an executable application.
    cs_app = cs_graph.compile(memory)
    # Invoke the graph with the necessary inputs to start the generation process.
    # Create a proper CSState object instead of a dictionary
    input_state: CSState = {
        "uuid": data.uuid,
        "source_path": user_info.get("source_path", ""),
        "cs_json_path": cs_json_path,
        "cs_csv_path": cs_csv_path,
        "json_language_analysis_path": json_language_analysis_path,
        "language": data.language,
        "project_info": data.project_info,
    }

    result = cs_app.invoke(
        input=input_state,
        config=config,
    )
    # Save file_dependency_lists from CS workflow result to user info
    file_dependency_lists = result.get("file_dependency_lists", [])
    if file_dependency_lists:
        user_info["file_dependency_lists"] = file_dependency_lists

    # Write the updated user information back to the file.
    write_user_info(user_info=user_info, file_path=str(user_path))

    # Read the generated JSON data to include in the response.
    try:
        sensitive = [
            "Module Description",
            "Data Flow",
            "Logic",
            "Module",
            "Function Description",
        ]
        with open(cs_json_path, "r", encoding="utf-8") as f:
            cs_data = json.load(f)

        cs_data = decrypt_sensitive_data(cs_data, sensitive_fields=sensitive)
        # Return a success response with the UUID and the generated document.
        return {"uuid": data.uuid, "doc_cs": cs_data}
    except Exception as e:
        # Return a standardized 500 error if reading the generated CS file fails.
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "error_code": "500",
                "message": f"Failed to load cs file: {e}",
            },
        )
