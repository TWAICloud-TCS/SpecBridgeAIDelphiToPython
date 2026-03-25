import json
import logging

logger = logging.getLogger(__name__)


def generate_code_prompt_harmony(
    group_context: dict,
    code_content: dict,
    language: str = "Delphi",
    project_info: str = "",
) -> str:
    """
    優化的群組基礎分析 Prompt - 使用 Harmony 格式
    基於 file_dependency_lists 的群組結構進行深度分析。

    Args:
        group_context (dict): 群組上下文資訊，包含檔案列表和群組資訊。
        code_content (dict): 包含程式碼的字典。
        language (str): 程式語言名稱 (例如: Delphi, Java, Python 等)。
        project_info (str): 用戶提供的系統描述資訊。

    Returns:
        str: 用於群組深度分析的優化提示。
    """
    
    # 格式化程式碼內容，支援多種檔案格式
    formatted_code_blocks = []
    if code_content:
        for filename, code in code_content.items():
            # 為每個檔案建立一個清晰的區塊，標明檔案名稱
            code_block = f"--- FILE: {filename} ---\n```\n{code}\n```"
            formatted_code_blocks.append(code_block)

        # 將所有程式碼區塊合併成一個大字串
        all_code_str = "\n\n".join(formatted_code_blocks)
    else:
        all_code_str = "無提供任何程式碼內容。"

    system_content = f"""你是 {language} 程式碼分析師，專精於函式分析和業務邏輯理解。
        推理: 高

        # 有效頻道: analysis, commentary, final。每個訊息都必須包含頻道。"""

    developer_content = f"""# 指令

        請分析程式碼群組中的每個函式，提取詳細的技術和業務資訊。

        分析步驟：
        1. 理解系統背景和模組職責
        2. 逐一分析每個函式或程序
        3. 詳細分析函式邏輯：
        - 識別所有輸入參數和資料來源
        - 列出所有處理的資料欄位（不要使用變數名稱，要用業務意義的名稱）
        - 識別所有輸出結果和後續動作
        - **深度挖掘隱藏資訊**：
          * 資料庫欄位名稱
          * 系統欄位
          * 使用者輸入欄位
          * 查詢條件欄位
          * 計算欄位和衍生欄位
        - **UI介面元素識別**：
          * 表單輸入欄位
          * 按鈕操作
          * 資料顯示元件
          * 選單和選項
        4. 為每個函式填寫：Module（檔案名稱）、Module Description（模組整體職責）、Function Description（函式核心目的）、Data Flow（資料流程：具體輸入欄位→處理動作→具體輸出結果）、Logic（詳細邏輯步驟，包含所有處理的欄位名稱）
        5. 彙總成 JSON 陣列

        要求：
        - 使用繁體中文
        - 輸出純 JSON 陣列，無其他文字
        - 專注程式碼邏輯，不憑空猜測
        - 不遺漏任何函式或程序
        - Data Flow 中必須使用業務意義的欄位名稱，不要使用程式變數名稱
        - Logic 中必須詳細列出所有處理的欄位，不要用「相關欄位」等概括性描述
        - 明確區分輸入欄位、處理動作和輸出結果
        - **完整性要求**：確保沒有遺漏任何在程式碼中提到的欄位
        - **UI介面完整性**：識別所有使用者介面元素
        - **隱藏資訊挖掘**：仔細檢查程式碼中的隱藏欄位和資訊

        輸出格式：
        ```json
        [
            {{
                "Module": "模組名稱",
                "Module Description": "模組職責",
                "Function Description": "函式功能",
                "Data Flow": "資料流程",
                "Logic": "處理邏輯"
            }}
        ]
        ```"""

    user_content = f"""專案背景：
        {project_info if project_info else "用戶未提供系統描述"}

        程式碼群組檔案：
        {json.dumps(group_context.get('group_files', []), ensure_ascii=False, indent=2)}

        程式碼內容：
        {all_code_str}

        請分析以上程式碼並輸出 JSON 陣列。"""

    return f"""<|start|>system<|message|>{system_content}<|end|>\n<|start|>developer<|message|>{developer_content}<|end|>\n<|start|>user<|message|>{user_content}<|end|>"""
