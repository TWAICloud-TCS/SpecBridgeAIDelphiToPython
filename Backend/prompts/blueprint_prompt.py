import json
import logging

logger = logging.getLogger(__name__)


def blueprint_prompt_harmony(intermediate_data, project_info: str | None = None):
    
    system_content = f"""你是一位系統分析師，專精於將程式結構轉換為使用者功能規格。
        推理: 高

        # 有效頻道: analysis, commentary, final。每個訊息都必須包含頻道。"""

    developer_content = f"""# 指令

        基於程式碼結構，歸納出以使用者為中心的高階功能規格。

        分析步驟：
        0. 請先理解專案背景描述，此為最高參考依據
        1. 以 description 欄位為最高權威，其他欄位與其衝突時以 description 為準
        2. 識別核心業務功能：
            - 找出完整的業務流程（如：疾病通報、統計查詢、資料維護等）
            - 避免將單一業務功能拆分成過多小功能
            - 專注於使用者完成一個完整業務目標所需的功能
        3. 整合相關操作：
            - 將同一業務流程中的多個函式整合成一個功能
            - 包含該流程的完整操作：查詢、新增、修改、刪除、列印等
            - 避免列出單獨的 UI 操作（如清除欄位、關閉視窗等）
        4. 提取完整欄位資訊：
            - 從程式碼結構的 Logic 和 Data Flow 中提取所有具體欄位名稱
            - 將程式碼結構中列出的所有欄位完整地包含在 input 中
            - 不要使用「其他欄位」、「相關欄位」等概括性描述
            - 必須列出程式碼結構中提到的每一個具體欄位名稱
            - **隱藏欄位挖掘**：仔細檢查 Logic 欄位中的隱藏資訊，包括：
            * 所有資料庫欄位名稱
            * 系統欄位和自動欄位
            * 使用者輸入欄位
            * 查詢條件欄位
            * 計算欄位和衍生欄位
            - **欄位清理**：移除英文變數名，只保留中文描述
            - **完整性檢查**：確保沒有遺漏任何在Logic中提到的欄位
            - **UI介面要求**：確保每個功能都有對應的使用者介面
            * 表單輸入欄位
            * 按鈕操作
            * 資料顯示
            * 選單和選項
        5. 撰寫功能規格：為每個業務功能填寫 name、description、input、output

            要求：
            - 使用繁體中文
            - 輸出純 JSON 陣列，無其他文字
            - 專注高階業務功能，避免技術細節
            - description 是唯一權威
            - 每個功能應該代表一個完整的業務流程，不要拆分成過多小功能
            - input 必須完整列出 CS document 中的所有具體欄位名稱，不要使用概括性描述
            - **欄位清理要求**：移除所有英文變數名，只保留中文描述
            - output 描述業務結果和產出，包含列印、通知等業務動作
            - 避免列出單獨的 UI 操作（如清除、關閉、驗證等）
            - 禁止在 input 中使用「其他欄位」、「相關欄位」等概括性描述
            - **UI介面完整性**：確保每個功能都包含完整的使用者介面元素
            * 輸入欄位：表單中的文字框、下拉選單等
            * 操作按鈕：儲存、查詢、列印、清除等
            * 資料顯示：表格、列表、報表等
            * 互動元素：選項、勾選框、按鈕等

        輸出格式：
        ```json
        [
            {{
                "name": "功能名稱",
                "description": "功能描述",
                "input": "完整列出 CS document 中的所有具體欄位名稱（移除英文變數名，只保留中文描述）",
                "output": "精確列出所有系統產出的結果和動作"
            }}
        ]
        ```"""

    user_content = f"""專案背景描述：
        {project_info if project_info else "用戶未提供系統描述"}

        程式結構資料：
        {json.dumps(intermediate_data, ensure_ascii=False, indent=2)}

        請分析以上程式結構並輸出功能規格 JSON 陣列。"""

    return f"""<|start|>system<|message|>{system_content}<|end|>\n<|start|>developer<|message|>{developer_content}<|end|>\n<|start|>user<|message|>{user_content}<|end|>"""
