import os
import zipfile, uuid
import aiofiles
from fastapi import UploadFile
from pathlib import Path, PurePosixPath
from typing import Union, Optional, Sequence, Tuple, Any, Dict, TypedDict, List
import chardet
from .file_extensions import EXCLUDED_EXTENSIONS
from .context_check import validate_delphi_file

CHUNK_SIZE = 1024 * 1024


def should_ignore(
    member: str,
    ignore_prefixes: Sequence[str] = ("__MACOSX/",),
    ignore_names: Sequence[str] = (".DS_Store",),
) -> bool:
    """
    Returns True if the given member should be ignored based on the specified blacklist.

    Parameters:
        member (str): The file or directory path to check.
        ignore_prefixes (Sequence[str]): A list of path prefixes (e.g., folders) that should be ignored.
        ignore_names (Sequence[str]): A list of exact file names that should be ignored.

    Returns:
        bool: True if the member matches any of the ignore rules (prefix or name); otherwise, False.
    """
    # Check if the path starts with any of the ignored prefixes (e.g., hidden system folders)
    if any(member.startswith(p) for p in ignore_prefixes):
        return True
    # Check if the file name matches any of the ignored names (e.g., hidden system files)
    if PurePosixPath(member).name in ignore_names:
        return True
    return False


def decode_filename(filename_bytes: bytes) -> str:
    """
    Attempt to decode filename bytes using various encodings common in Traditional Chinese systems.

    Args:
        filename_bytes (bytes): The raw bytes of the filename to decode

    Returns:
        str: The decoded filename
    """
    # List of encodings to try, in order of preference
    encodings = [
        "cp950",  # Windows Traditional Chinese
        "big5",  # Traditional Chinese
        "big5hkscs",  # Hong Kong Traditional Chinese
        "gb18030",  # Unified Chinese encoding
        "utf-8",  # Standard UTF-8
        "utf-8-sig",  # UTF-8 with BOM
    ]

    # First try chardet for automatic detection
    detected = chardet.detect(filename_bytes)
    if detected and detected["confidence"] > 0.8 and detected["encoding"] is not None:
        try:
            return filename_bytes.decode(detected["encoding"])
        except:
            pass

    # Try each encoding in our list
    for encoding in encodings:
        try:
            return filename_bytes.decode(encoding)
        except:
            continue

    # If all else fails, try cp437 (ZIP default) and replace invalid chars
    return filename_bytes.decode("cp437", errors="replace")


def read_zip_to_fs_json(
    zip_path: Union[str, Path],
    project_name: Union[str, None] = None,
    ignore_prefixes: Sequence[str] = ("__MACOSX/",),
    ignore_names: Sequence[str] = (".DS_Store",),
) -> dict:
    """
    Generate a file system structure in JSON format from the contents of a ZIP file,
    automatically ignoring specified system files or folders.

    Parameters:
        zip_path (Union[str, Path]): Path to the ZIP file to be read.
        project_name (Union[str, None]): Optional name for the root of the file tree.
                                         If not provided, it defaults to the ZIP file name (without extension).
        ignore_prefixes (Sequence[str]): Folder name prefixes to ignore (e.g., "__MACOSX/").
        ignore_names (Sequence[str]): File names to ignore (e.g., ".DS_Store").

    Returns:
        dict: A nested dictionary representing the folder/file hierarchy of the ZIP archive.
              Each node has a 'name', 'type' ("file" or "folder"), and optionally 'children'.
    """
    zip_path = Path(zip_path)
    project_name = project_name or zip_path.stem

    root = {"name": project_name, "type": "folder", "children": []}
    nodes: Dict[str, Any] = {"": root}

    with zipfile.ZipFile(zip_path) as zf:
        for member_info in zf.infolist():
            # Convert filename to bytes and attempt to decode
            filename_bytes = member_info.filename.encode("cp437")
            member = decode_filename(filename_bytes)

            if should_ignore(member, ignore_prefixes, ignore_names):
                continue

            path = PurePosixPath(member)
            parts = path.parts
            accum = ""

            for i, part in enumerate(parts):
                accum = f"{accum}/{part}".lstrip("/")
                if accum in nodes:
                    continue

                node_type = (
                    "folder" if i < len(parts) - 1 or member.endswith("/") else "file"
                )
                node: Dict[str, Any] = {"name": part, "type": node_type}
                if node_type == "folder":
                    node["children"] = []

                parent_path = "/".join(parts[:i])
                parent_children = nodes[parent_path]["children"]
                parent_children.append(node)
                nodes[accum] = node

    return root


def unzip_to_directory(
    logger,
    zip_path: Union[str, Path],
    out_dir: Union[str, Path],
    uuid_str: Optional[str] = None,
    overwrite: bool = False,
) -> Union[Path, str]:
    """
    Extracts the contents of a ZIP archive (zip_path) into the specified output directory (out_dir).

    Behavior:
    - If `overwrite=False` and the target file already exists, a ValueError is raised.
    - Includes built-in Zip Slip protection: rejects entries containing '..' or absolute paths.

    Parameters:
        zip_path (Union[str, Path]): Path to the ZIP file.
        out_dir (Union[str, Path]): Destination directory for extraction.
        uuid_str (Optional[str]): An optional unique subdirectory name (e.g., for isolation).
        overwrite (bool): Whether to overwrite existing files. Defaults to False.
    """
    zip_path = Path(zip_path)
    out_dir = Path(out_dir) / uuid_str if uuid_str else Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    unzip_folder = ""
    with zipfile.ZipFile(zip_path) as zf:
        for i, member_info in enumerate(zf.infolist()):
            # Convert filename to bytes and attempt to decode
            filename_bytes = member_info.filename.encode("cp437")
            member_filename = decode_filename(filename_bytes)

            member_path = Path(member_filename)

            # Skip ignored system files
            if should_ignore(member_filename):
                continue

            # Zip Slip protection
            if member_path.is_absolute() or ".." in member_path.parts:
                raise ValueError(f"Insecure zip entry: {member_filename}")

            target = out_dir / member_filename

            if i < 1:
                unzip_folder = target
            # Check for overwrite protection
            if not overwrite and target.exists():
                raise ValueError(f"File exists: {target}")

            # Create directories or extract files
            if member_info.is_dir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)

                with zf.open(member_info) as src, target.open("wb") as dst:
                    dst.write(src.read())

                if not validate_delphi_file(str(target), logger):
                    logger.error(
                        f"[ Unzip ] Invalid Delphi file detected, skipping: {target}"
                    )
                    raise ValueError(f"Invalid Delphi file: {target}")
    return unzip_folder


def make_safe_path(raw_filename: str, dir: str) -> Tuple[Path, str]:
    """
    Generate a safe, non-conflicting file path for saving, preserving the original file extension.

    Parameters:
        raw_filename (str): The original file name (used to extract the file extension).
        dir (str): The directory where the file should be saved.

    Returns:
        Tuple[Path, str]: A tuple containing the generated safe Path and the UUID string used.
    """
    suffix = Path(raw_filename).suffix
    uuid_str = uuid.uuid4().hex
    safe_path = f"{dir}/{uuid_str}{suffix}"
    return Path(safe_path), uuid_str


async def save_upload_file_async(
    upload_file: UploadFile, dst: Union[str, Path]
) -> None:
    """
    Asynchronously save a FastAPI UploadFile to disk.

    This function reads and writes the file in chunks to avoid loading the entire file into memory.

    Parameters:
        upload_file (UploadFile): The uploaded file object from FastAPI.
        dst (Union[str, Path]): The destination path to write the file to.

    Returns:
        None
    """
    dst = Path(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)

    async with aiofiles.open(dst, "wb") as out_file:
        await upload_file.seek(0)
        while True:
            chunk = await upload_file.read(CHUNK_SIZE)
            if not chunk:
                break
            await out_file.write(chunk)


def open_all_file(folder_path):
    folder_path = Path(folder_path)

    # Remove files with extensions in EXCLUDED_EXTENSIONS from the folder
    for ext in EXCLUDED_EXTENSIONS:
        for file in folder_path.rglob(f"*.{ext}"):
            try:
                file.unlink()
            except Exception:
                pass
    code_string = ""
    for path in sorted(folder_path.rglob("*")):
        if path.is_file():
            # Try CP950 first (Windows Big-5 superset), then Big-5, then HKSCS
            for enc in ("cp950", "big5", "big5hkscs", "utf-8-sig", "utf-8"):
                try:
                    with open(path, "r", encoding=enc) as f:
                        text = f.read()
                    code_string += text
                    break
                except UnicodeDecodeError:
                    continue

    return code_string
