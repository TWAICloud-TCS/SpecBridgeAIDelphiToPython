import io
import zipfile
import json

from fastapi import APIRouter, File, UploadFile, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse
from pathlib import Path
from utils.api_parser import SaveParser
from utils.zip_utils import (
    save_upload_file_async,
    make_safe_path,
    read_zip_to_fs_json,
    unzip_to_directory,
    open_all_file,
)
from utils.file_extensions import is_delphi_file
from utils.tools import token_count, write_user_info, update_doc_path
from utils.logger import get_uuid_logger
from utils.paths import (
    UPLOAD_DIR,
    USER_DIR,
    get_chunk_output_dir,
    get_unzip_dir,
    get_output_doc_dir,
)
from utils.encryption import encrypt_sensitive_data, decrypt_sensitive_data
from utils.auth_token import generate_token, verify_token
from utils.response_csv import convert_jsondata_to_csv
from src.sa import generate_sa_txt

# Initialize FastAPI router for file handling endpoints
router = APIRouter(
    prefix="/file",
    tags=["File handler"],
)


@router.post("/upload")
async def upload(file: UploadFile = File(...)):
    """
    Handle file upload by client, extract zip contents, and record user context.

    1. Saves the incoming ZIP file to a unique path under `uploads/`.
    2. Reads and returns a JSON representation of the zip's file tree.
    3. Extracts files into `unzipped/{uuid}` directory.
    4. Opens all extracted files and computes total token count.
    5. Persists user metadata (uuid and source path) to `users/{uuid}`.

    Args:
        file (UploadFile): Uploaded ZIP file.

    Returns:
        dict: Response containing status, file info, token size, and file tree structure.

    Raises:
        HTTPException: If any step in saving, reading, or extracting fails.
    """
    # Check if the uploaded file has a valid name and .zip extension
    if file.filename is None:
        return JSONResponse(
            status_code=400,
            content={
                "status": "error",
                "error_code": "400",
                "message": "Uploaded file must have a filename",
            },
        )
    if not file.filename.lower().endswith(".zip"):
        return JSONResponse(
            status_code=400,
            content={
                "status": "error",
                "error_code": "400",
                "message": "Only .zip files are allowed for upload",
            },
        )
    # Generate a unique safe path for the uploaded file
    upload_path, uuid_str = make_safe_path(file.filename, dir=str(UPLOAD_DIR))
    logger = get_uuid_logger(uuid_str)

    # Path to store user-specific metadata JSON
    user_info_path = Path(USER_DIR, uuid_str)
    token, expire_time = generate_token(uuid_str)
    try:
        # Async save the uploaded file to disk
        await save_upload_file_async(file, upload_path)

        logger.info("[ File ] get file")
        # Build a JSON tree of the ZIP archive contents
        tree = read_zip_to_fs_json(upload_path)

        logger.info("[ File ] unzip and file")

        # Extract the ZIP file into a user-specific subfolder
        unzip_dir = get_unzip_dir(uuid_str)
        unzip_folder = unzip_to_directory(
            logger, upload_path, unzip_dir.parent, uuid_str, overwrite=True
        )

        # Check if there are any Delphi-related files in the extracted folder
        has_delphi_files = False
        for file_path in Path(unzip_folder).rglob("*"):
            if file_path.is_file() and is_delphi_file(file_path.name):
                has_delphi_files = True
                break

        if not has_delphi_files:
            logger.error("[ File ] No Delphi-related files found in uploaded archive")

            return JSONResponse(
                status_code=400,
                content={
                    "status": "error",
                    "error_code": "400",
                    "message": "Uploaded file error: No Delphi-related files (.pas, .dpr, .dfm) found in the zip archive",
                },
            )

        # Read all extracted files into a combined text context
        context = open_all_file(unzip_folder)

        # Count tokens in the combined context for LLM budgeting
        token_size = token_count(context)

        # Extract project name from filename (remove extension)
        project_name = Path(file.filename).stem

        # Save user metadata for downstream operations
        write_user_info(
            user_info={
                "uuid": uuid_str,
                "source_path": str(unzip_folder),
                "project_name": project_name,
            },
            file_path=str(user_info_path),
        )

        logger.info("[ File ] file uploaded final")

    except Exception as e:
        # Return a 500 error if anything goes wrong
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "error_code": "500",
                "message": f"Failed to save file: {e}",
            },
        )

    # Construct and return a detailed response
    return {
        "status": HTTPException(status_code=200, detail="File uploaded successfully"),
        "uuid": uuid_str,
        "token": token,
        "token_expire_time": expire_time.isoformat(),
        "original_name": file.filename,
        "saved_to": str(upload_path),
        "size_bytes": upload_path.stat().st_size,
        # Multiply token count by 2 as a rough context estimate
        "token_size": token_size * 2,
        "file_tree": tree,
    }


@router.post("/saver")
async def saver(data: SaveParser):
    """
    Saves the user-modified document and records feedback.
    Example of the expected JSON format:
    {
        "uuid":"12345",
        "doc_data":[
        {
            "Project": "content",
            "Module": "content",
            ...
        },
        ...
        ],
        "doc_name":"cs" or "sa" or "bp",
        "csat": 5,
        "suggestion": "good"
    }
    """

    verify_token(data.uuid, data.token, expire_time=data.expire_time)

    sensitive_fields_map = {
        "cs": [
            "Module Description",
            "Data Flow",
            "Logic",
            "Module",
            "Function Description",
        ],
        "sa": ["title", "content"],
        "bp": ["name", "description", "input", "output"],
    }

    # Get a logger based on the UUID from the request
    logger = get_uuid_logger(data.uuid)
    # Construct the path to the user's information file
    user_path = Path(USER_DIR, data.uuid)
    # Read the existing user information
    with open(user_path, "r", encoding="utf-8") as f:
        user_info = json.load(f)

    # Determine which document path to update based on doc_name
    if data.doc_name == "cs":
        path = user_info.get("cs_json_path", "")
        # Generate a new path with an "_updated" suffix
        new_path = update_doc_path(path)
        # Record the updated path in the user info
        user_info["cs_json_path_updated"] = new_path
        sensitive_fields = sensitive_fields_map.get("cs", [])

    elif data.doc_name == "sa":
        path = user_info.get("sa_txt_path", "")
        new_path = update_doc_path(path)
        user_info["sa_txt_path_updated"] = new_path
        sensitive_fields = sensitive_fields_map.get("sa", [])

    elif data.doc_name == "bp":
        path = user_info.get("blueprint_json_path", "")
        new_path = update_doc_path(path)
        user_info["blueprint_json_path_updated"] = new_path
        sensitive_fields = sensitive_fields_map.get("bp", [])
    else:
        # If doc_name is invalid, return an error
        return JSONResponse(
            status_code=400,
            content={
                "status": "error",
                "error_code": "400",
                "message": "Invalid doc_name, must be 'cs', 'sa', or 'bp'",
            },
        )

    try:
        # Encrypt sensitive fields in the document data
        data.doc_data = encrypt_sensitive_data(data.doc_data, sensitive_fields)
        # Write the user-submitted document data to the new path
        with open(new_path, "w", encoding="utf-8") as f:
            json.dump(data.doc_data, f, ensure_ascii=False, indent=2)

        logger.info(f"[ File ] save to {new_path}")
    except Exception as e:
        # If writing the file fails, log the error and return an error response
        logger.error(f"[ File ] Failed to save file: {e}")
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "error_code": "500",
                "message": f"Failed to save file: {e}",
            },
        )

    # Store the customer satisfaction score and suggestion in the user info
    user_info["csat"] = data.csat
    user_info["suggestion"] = data.suggestion

    # Write the updated user information back to the file
    write_user_info(user_info=user_info, file_path=str(user_path))
    # Return a success status
    return {"status": HTTPException(status_code=200, detail="File saved successfully")}


@router.get("/download/{token}/{expire_time}/{uuid}")
async def download_merged_files(uuid: str, token: str, expire_time: str):
    """
    Download a zip file containing the merged files for a specific UUID.
    Files are decrypted before being added to the zip.

    Args:
        uuid (str): Unique identifier for the user's files.
        token (str): Download token for authentication.
    Returns:
        StreamingResponse: A response containing the zip file with decrypted content.

    Raises:
        HTTPException: If the files don't exist or there's an error creating the zip.
    """

    sensitive_fields_map = {
        "cs": [
            "Module Description",
            "Data Flow",
            "Logic",
            "Module",
            "Function Description",
        ],
        "sa": ["title", "content"],
        "bp": ["name", "description", "input", "output"],
    }

    # Verify token before processing
    verify_token(uuid, token, expire_time=expire_time)

    source_dir = Path(f"{get_chunk_output_dir(uuid)}/final_merged")
    output_doc_dir = get_output_doc_dir(uuid)

    # Check if the directory exists
    if not source_dir.exists() or not source_dir.is_dir():
        return JSONResponse(
            status_code=404,
            content={
                "status": "error",
                "error_code": "404",
                "message": f"Files not found for UUID: {uuid}",
            },
        )

    # Create an in-memory file to store the zip
    zip_buffer = io.BytesIO()

    # Logger for tracking operations
    logger = get_uuid_logger(uuid)

    try:

        # Create a zip file in the buffer
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            # Walk through the directory and add all files to the zip
            # Include files from output_doc directory if it exists
            if source_dir.exists() and source_dir.is_dir():
                for file_path in source_dir.glob("**/*"):
                    if file_path.is_file():
                        rel_path = Path("final_merged") / file_path.relative_to(
                            source_dir
                        )
                        zf.write(file_path, rel_path)
                        logger.info(f"[ File ] Added from source_dir: {rel_path}")
            if output_doc_dir.exists() and output_doc_dir.is_dir():
                for file_path in output_doc_dir.glob("**/*"):
                    if file_path.is_file():
                        rel_path = Path("output_doc") / file_path.relative_to(
                            output_doc_dir
                        )

                        # Determine document type from filename
                        doc_type = None
                        filename_lower = file_path.name.lower()
                        if "cs" in filename_lower:
                            doc_type = "cs"
                        elif "sa" in filename_lower:
                            doc_type = "sa"
                        elif "blueprint" in filename_lower or "bp" in filename_lower:
                            doc_type = "bp"

                        # Try to decrypt if document type identified
                        if doc_type:
                            try:
                                file_ext = file_path.suffix.lower()

                                # Handle JSON files
                                if file_ext == ".json":
                                    with open(file_path, "r", encoding="utf-8") as f:
                                        data = json.load(f)

                                    if isinstance(data, list):
                                        sensitive_fields = sensitive_fields_map.get(
                                            doc_type, []
                                        )
                                        decrypted_data = decrypt_sensitive_data(
                                            data, sensitive_fields
                                        )

                                        decrypted_json = json.dumps(
                                            decrypted_data, ensure_ascii=False, indent=2
                                        )
                                        zf.writestr(str(rel_path), decrypted_json)
                                        logger.info(
                                            f"[ File ] Decrypted JSON and added: {rel_path}"
                                        )
                                        if doc_type == "cs":
                                            # Also convert to CSV and add to zip
                                            csv_content = convert_jsondata_to_csv(
                                                json_data=decrypted_data
                                            )
                                            csv_rel_path = rel_path.with_suffix(".csv")
                                            zf.writestr(
                                                str(csv_rel_path),
                                                csv_content.to_csv(index=False),
                                            )
                                            logger.info(
                                                f"[ File ] Converted to CSV and added: {csv_rel_path}"
                                            )
                                        if doc_type == "sa":
                                            # Also generate SA text file and add to zip
                                            sa_txt_content = generate_sa_txt(
                                                decrypted_data
                                            )
                                            sa_txt_rel_path = rel_path.with_suffix(
                                                ".txt"
                                            )
                                            if sa_txt_content:
                                                # Convert to string if it's a list or other type
                                                if isinstance(sa_txt_content, list):
                                                    sa_txt_str = "\n".join(
                                                        str(item)
                                                        for item in sa_txt_content
                                                    )
                                                else:
                                                    sa_txt_str = str(sa_txt_content)
                                                zf.writestr(
                                                    str(sa_txt_rel_path), sa_txt_str
                                                )
                                                logger.info(
                                                    f"[ File ] Generated SA text and added: {sa_txt_rel_path}"
                                                )

                                # Other file types
                                else:
                                    zf.write(file_path, rel_path)

                            except Exception as e:
                                logger.warning(
                                    f"[ File ] Could not decrypt {file_path}: {e}, adding original"
                                )
                                zf.write(file_path, rel_path)
                        else:
                            # No document type identified, add as-is
                            zf.write(file_path, rel_path)

        logger.info(f"[ File ] Created zip of decrypted merged files for {uuid}")

        # Seek to the beginning of the buffer for reading
        zip_buffer.seek(0)

        # Create a filename for the download
        filename = f"download_{uuid}.zip"

        # Return the zip file as a streaming response
        return StreamingResponse(
            zip_buffer,
            media_type="application/zip",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    except Exception as e:
        logger.error(f"[ File ] Failed to create decrypted zip file: {e}")
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "error_code": "500",
                "message": f"Failed to create zip file: {e}",
            },
        )
