import json

def generate_language_analysis_prompt(coding_language: str = "Delphi") -> str:
    """
    Generate prompt for analyzing coding language dependencies
    """
    return f"""你是一個 {coding_language} 程式語言分析專家。

**任務目標：**
分析 {coding_language} 程式碼中的檔案依賴關係，識別關鍵字和檔案類型。

**分析要求：**
1. 找出核心程式碼檔案的副檔名
2. 識別表示檔案間依賴關係的關鍵字
3. 識別該語言的註解語法（單行註解和多行註解）

**範例參考：**
- Python: .py 檔案中的 "import", "from ... import"，註解使用 "#" (單行) 
- Java: .java 檔案中的 "import", "package"，註解使用 "//" (單行) 和 "/* */" (多行)
- C++: .cpp 檔案中的 "#include"，註解使用 "//" (單行) 和 "/* */" (多行)

**輸出格式：**
```json
{{
    "coding_language": "{coding_language}",
    "dependency_patterns": [
        {{
            "file_extension": ".副檔名",
            "dependency_keywords": ["關鍵字1", "關鍵字2", ...],
            "description": "簡短說明這些關鍵字如何表示檔案間的依賴關係"
        }}
    ],
    "comment_syntax": {{
        "single_line": ["單行註解符號1", "單行註解符號2", ...],
        "multi_line_start": ["多行註解開始符號1", "多行註解開始符號2", ...],
        "multi_line_end": ["多行註解結束符號1", "多行註解結束符號2", ...]
    }}
}}
```

**重要原則：**
- 只關注核心程式碼檔案（.pas, .py, .java, .cpp 等）
- 只包含直接表示檔案依賴的關鍵字
- 排除配置檔案、資源檔案、建置檔案
- 排除編譯器指令和除錯資訊

**分析重點：**
- 模組/類別導入關鍵字
- 主程式檔案識別
- 檔案間引用關係

**語言要求：**
- 所有描述都必須使用繁體中文

請確保輸出純 JSON 格式，不要其他解釋文字。"""


def generate_function_extraction_prompt(file_content: str, file_name: str, coding_language: str = "Delphi") -> str:
    """
    Generate prompt for extracting function names from a file
    """
    return f"""你是一個 {coding_language} 程式碼分析專家。

**任務目標：**
分析以下檔案，提取所有函數名稱。

**檔案資訊：**
- 檔案名稱: {file_name}
- 程式語言: {coding_language}

**檔案內容：**
{file_content}

**輸出格式：**
```json
{{
    "file_name": "{file_name}",
    "function_names": ["函數名稱1", "函數名稱2", "函數名稱3", ...]
}}
```

**提取要求：**
1. 找出所有函數、程序、方法、類別
2. 只提取名稱，不需要詳細資訊
3. 包含所有類型的函數定義
4. **每個函數名稱只出現一次**（自動去除重複）
5. 如果函數同時有宣告（declaration）和實作（implementation），只記錄一次

**語言要求：**
- 所有描述都必須使用繁體中文

請確保輸出純 JSON 格式，不要其他解釋文字。"""


def generate_dependency_mapping_prompt(
    file_contents: dict, 
    function_mapping: dict,
    file_extensions: list, 
    keywords: list,
    coding_language: str = "Delphi"
) -> str:
    """
    Generate prompt for mapping dependencies between files
    """
    return f"""你是一個 {coding_language} 程式依賴關係分析專家。

**任務目標：**
分析檔案間的依賴關係，建立依賴映射。

**分析資訊：**
- 檔案副檔名: {file_extensions}
- 依賴關鍵字: {keywords}
- 檔案內容: {file_contents}
- 函數映射: {function_mapping}

**分析步驟：**
1. 檢查每個檔案中的依賴關鍵字
2. 提取關鍵字後的名稱
3. 判斷名稱類型：
   - 檔案名稱：直接使用（如 "FRMDM" → "FRMDM.pas"）
   - 函數名稱：在函數映射中查找所屬檔案
4. 建立檔案間的依賴關係

**輸出格式：**
```json
{{
    "file_dependencies": [
        {{
            "file": "檔案名稱",
            "dependent_on": ["依賴的檔案1", "依賴的檔案2", ...]
        }}
    ]
}}
```

**重要要求：**
1. 只輸出檔案名稱，不包含函數名稱
2. 準確識別所有依賴關係
3. 包含獨立檔案（dependent_on 為空陣列）
4. 輸出純 JSON 格式

**語言要求：**
- 所有描述都必須使用繁體中文

請現在開始分析並輸出結果。"""
