import magic
import os

from regex import F


# --- 2. 驗證核心邏輯 ---
def validate_delphi_file(file_path: str, logger):
    # 檢查是否為資料夾
    if os.path.isdir(file_path):
        logger.info(f"路徑是資料夾，跳過檢查: {file_path}")
        return True

    # 檢查是否為檔案
    if not os.path.isfile(file_path):
        logger.error(f"路徑不是有效的檔案: {file_path}")
        return False
    # 允許的 MIME 類型清單
    # 注意：Delphi 原始碼常被識別為 text/plain，所以必須包含它，稍後再做內容檢查
    ALLOWED_MIMES = [
        "text/x-pascal",
        "text/x-delphi-source",
        "text/plain",
        "application/octet-stream",
        "application/x-wine-extension-ini",  # .dof files
    ]

    # Delphi 特徵關鍵字 (用於複查 text/plain)
    DELPHI_KEYWORDS = [
        b"unit ",
        b"program ",
        b"library ",
        b"package ",  # Source headers
        b"object ",
        b"inherited ",  # DFM text format
        b"TPF0",  # DFM binary header
    ]

    logger.info(f"正在檢查檔案: {file_path} ...")

    # 只讀取開頭 2048 bytes 足夠進行 magic 判斷，節省記憶體
    if not os.path.exists(file_path):
        logger.error(f"File not found on server: {file_path}")
        return False

    with open(file_path, "rb") as f:
        header_content = f.read(2048)

    # 使用 mime=True 獲取 "text/plain" 這種格式
    mime_type = magic.from_buffer(header_content, mime=True)
    logger.info(f"-> Libmagic 識別結果: {mime_type}")

    if mime_type not in ALLOWED_MIMES:
        logger.error(f"檔案類型錯誤 ({mime_type})。請上傳 Delphi 檔案。")
        return False
    if mime_type == "text/plain":
        # 因為 'text/plain' 太寬泛了，我們必須確認內容真的像 Delphi
        is_delphi_content = False

        # 將內容轉為小寫以進行不分大小寫的比對
        content_lower = header_content.lower()

        for keyword in DELPHI_KEYWORDS:
            if keyword.lower() in content_lower:
                is_delphi_content = True
                logger.info(f"-> 發現 Delphi 特徵關鍵字: {keyword.decode()}")
                break

        if not is_delphi_content:
            # 雖然是文字檔，但看起來不像 Delphi 程式碼
            logger.error("檔案內容不符 Delphi 格式，缺少關鍵字。")
            return False

    return True
