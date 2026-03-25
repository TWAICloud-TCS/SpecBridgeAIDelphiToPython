import json

from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.memory import MemorySaver
from fastapi import APIRouter
from fastapi.responses import JSONResponse

from graph.bp_graph import BPGraph
from state.state import BPState
from utils.api_parser import RuleData
from utils.llm import get_llm_client
from utils.tools import write_user_info
from utils.paths import USER_DIR
from utils.auth_token import verify_token, decrypt_aes_gcm
from utils.encryption import decrypt_sensitive_data

router = APIRouter(
    prefix="/bp",
    tags=["Blueprint"],
)


@router.post("/document")
def blueprint(data: RuleData):
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

    Handles a POST request to initiate the code translation process for a user.

    This endpoint receives a user's UUID and an API key. It then loads the user's
    session data, sets up and executes a LangChain graph (`CTGraph`) to perform
    the core translation logic, and finally updates the user's session data with
    the paths to the generated output files.

    Args:
        data (RuleData): The request body containing the user's UUID and API key,
                         validated by a Pydantic model.
    """
    # --- 1. Initialization and User Data Loading ---

    # Construct the path to the user's persistent information file.

    verify_token(data.uuid, data.token, expire_time=data.expire_time)

    user_path = USER_DIR / f"{data.uuid}"
    # Load the user's data, which includes paths to their source code and intermediary files.
    with open(user_path, "r", encoding="utf-8") as f:
        user_info = json.load(f)

    # --- 2. AI Model and Graph Setup ---

    # Select and initialize the language model using the provided API key.
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
    # Initialize a memory component to manage state or history within the graph.
    memory = MemorySaver()

    # Instantiate the core processing logic defined as a LangChain graph.
    bp_graph = BPGraph()

    # Configure the graph execution environment. This allows passing dynamic

    config: RunnableConfig = {"configurable": {"thread_id": data.uuid, "model": llm}}
    # --- 3. Graph Execution ---

    # Compile the graph with the memory component to create an executable application.
    bp_app = bp_graph.compile(memory)

    input_state: BPState = {
        "uuid": data.uuid,
        "source_path": user_info["source_path"],
        "cs_original_path": user_info.get("cs_json_path", ""),
        "cs_json_path": user_info.get("cs_json_path_updated"),
        "project_info": data.project_info,
        "bp_sensitive": ["name", "description", "input", "output"],
    }

    result = bp_app.invoke(
        input=input_state,
        config=config,
    )

    # --- 4. Storing Results ---

    developers_output_path = result.get("developers_output_path", "")
    blueprint_json_path = result.get("blueprint_json_path", "")

    user_info["developers_output_path"] = str(developers_output_path)
    user_info["blueprint_json_path"] = str(blueprint_json_path)

    # Persist the updated user information back to their file for future reference.
    write_user_info(user_info=user_info, file_path=str(user_path))

    # Read the generated JSON data to include in the response.
    try:
        with open(blueprint_json_path, "r", encoding="utf-8") as f:
            bp_data = json.load(f)

        bp_data = decrypt_sensitive_data(
            bp_data, sensitive_fields=["name", "description", "input", "output"]
        )

        # Return a success response with the UUID and the generated document.
        return {
            "uuid": data.uuid,
            "doc_bp": bp_data,
        }
    except Exception as e:
        # Return a standardized 500 error if reading the generated BP file fails.
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "error_code": "500",
                "message": f"Failed to load bp file: {e}",
            },
        )
