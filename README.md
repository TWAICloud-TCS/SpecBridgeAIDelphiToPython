# SpecBridgeAI-Refactoring_Delphi_into_Python_Flask

## 專案簡介
SpecBridgeAI-Refactoring_Delphi_into_Python_Flask 是一個基於 AI 驅動的強大平台，專為協助舊有系統遷移到現代 Python Flask Web 應用程式而設計。該平台運用先進的大型語言模型 (LLM) 來分析來自不同程式語言的原始碼，建立中介文件和系統分析 (SA) 文件，並產生等效的 Flask 實作，同時保持業務邏輯和功能完整性。

## 主要特色
- **程式碼翻譯**: 將多種程式語言 (PHP、Delphi、Java 等) 轉換為 Python Flask
- **系統分析文件生成**: 自動產生完整的 SA 文件
- **多種 AI 模型支援**: 支援 Claude、GPT、Gemini、DeepSeek 等多種 LLM
- **分塊處理**: 將大型程式碼基礎分割成可管理的區塊進行處理
- **網頁介面**: 提供友善的網頁 UI 供程式碼上傳和轉換
- **命令列介面**: 支援腳本操作，便於整合到工作流程中
- **中介文件**: 產生原始碼的結構化文件
- **詳細記錄**: 完整的記錄系統追蹤翻譯過程
- **Blueprint 生成**: 建立 Flask blueprints 以實現模組化應用程式架構
- **LangGraph 工作流**: 使用 LangGraph 框架管理複雜的 AI 處理流程

## 系統需求

- Python 3.9+
- Docker (可選，用於容器化部署)
- 支援的 AI 模型 API 金鑰存取權限
- 最少 4GB RAM (建議 8GB+ 用於大型專案)
- 10GB+ 可用磁碟空間
- 支援的作業系統：Windows、macOS、Linux

## 安裝步驟

### 方法 1: 標準安裝

1. 複製儲存庫：
```bash
git clone https://github.com/TWAICloud-TCS/SpecBridgeAI-Refactoring_Delphi_into_Python_Flask.git
cd SpecBridgeAI-Refactoring_Delphi_into_Python_Flask
```

2. 安裝必要的相依性：
```bash
pip install -r Backend/requirements.txt
```

3. 配置環境變數 (透過網頁介面輸入 API 金鑰)

### 方法 2: Docker 安裝

1. 複製儲存庫：
```bash
git clone https://github.com/TWAICloud-TCS/SpecBridgeAI-Refactoring_Delphi_into_Python_Flask.git
cd SpecBridgeAI-Refactoring_Delphi_into_Python_Flask
```

2. 使用 Docker Compose 建置和執行：
```bash
docker-compose up -d
```

## 使用方法

### 網頁介面

1. 啟動 FastAPI 網頁應用程式：
```bash
cd Backend
python app.py
```

2. 開啟瀏覽器並前往 `http://localhost:5001`

3. 依照網頁介面的步驟操作：
   - 上傳原始碼檔案或 ZIP 壓縮檔
   - 選擇 AI 模型以生成中介文件
   - 產生中介文件
   - 檢視並調整文件內容 (如需要)
   - 選擇 AI 模型進行程式碼翻譯
   - 產生 Flask 應用程式碼
   - 下載最終輸出結果

## 專案架構

- [`Backend/`](Backend/): 伺服器端程式碼
  - `app.py`: 主要的 FastAPI 應用程式
  - `router/`: API 路由處理器
    - `file_handler.py`: 檔案上傳和管理端點
    - `csbot.py`: 程式碼掃描端點
    - `sabot.py`: 系統分析端點
    - `ctbot.py`: 程式碼翻譯端點 (單執行緒)
    - `mtbot.py`: 多執行緒翻譯端點
    - `bpbot.py`: Blueprint 生成端點
  - `prompts/`: AI 模型的提示範本
  - `graph/`: LangGraph 工作流程定義
    - `cs_graph.py`: 程式碼掃描圖
    - `sa_graph.py`: 系統分析圖
    - `ct_graph.py`: 程式碼翻譯圖
    - `mt_graph.py`: 多執行緒圖
    - `bp_graph.py`: Blueprint 生成圖
    - `preprocess_graph.py`: 前處理圖
  - `src/`: 核心處理邏輯
    - `cs.py`: 程式碼結構分析
    - `sa.py`: 系統分析處理
    - `ct.py`: 程式碼翻譯處理
    - `mt.py`: 多執行緒翻譯處理
    - `bp.py`: Blueprint 生成處理
    - `preprocess.py`: 前處理邏輯
  - `utils/`: 輔助函式
    - `llm.py`: LLM 模型選擇和配置
    - `tools.py`: 通用工具函式
    - `logger.py`: 記錄系統
    - `zip_utils.py`: ZIP 檔案處理
    - `file_extensions.py`: 檔案類型處理
  - `state/`: 狀態管理
    - `state.py`: LangGraph 狀態定義
  - `test/`: 測試檔案

- [`Frontend/`](Frontend/): 客戶端程式碼
  - `static/`: 靜態資源 (Vue.js SPA)
    - `index.html`: 主要 HTML 檔案
    - `assets/`: 靜態資源 (JS、CSS、圖片)

- [`docker-compose.yml`](docker-compose.yml): Docker 容器編排設定

## 翻譯流程

1. **檔案上傳**: 使用者透過網頁介面上傳原始碼檔案或 ZIP 壓縮檔
2. **前處理**: 系統分析程式碼結構，識別程式語言，並將其分割成可管理的區塊
3. **程式碼掃描**: 使用 LangGraph 工作流程分析檔案相依性和結構
4. **系統分析**: AI 模型產生原始程式碼的結構化文件
5. **Blueprint 生成**: 系統分析業務邏輯並建立 Flask 應用程式架構藍圖
6. **程式碼翻譯**: AI 模型將原始程式碼翻譯為 Python Flask 實作
7. **整合輸出**: 將翻譯結果整合並包裝成完整的 Flask 應用程式供下載

### 支援的翻譯路徑
- **單執行緒翻譯** (`/ct/translator`): 適合小型專案的順序處理
- **多執行緒翻譯** (`/mt/translator`): 適合大型專案的平行處理，提升效率

## API 端點

### 檔案管理
- `POST /api/file/upload`: 上傳檔案或 ZIP 壓縮檔
- `POST /api/file/saver`: 儲存專案資訊

### 程式碼處理工作流程
- `POST /api/cs/document`: 程式碼結構分析和中介文件生成
- `POST /api/sa/document`: 系統分析文件生成
- `POST /api/bp/generator`: Blueprint 藍圖生成
- `POST /api/ct/translator`: 單執行緒程式碼翻譯
- `POST /api/mt/translator`: 多執行緒程式碼翻譯

## 支援的程式語言

### 輸入語言
- Delphi (主要支援)

### 輸出語言
- Python Flask (主要輸出格式)
- 結構化 HTML/CSS/JavaScript 前端

## 技術架構

### 後端技術棧
- **FastAPI**: 高效能的 Python Web 框架
- **LangGraph**: AI 工作流程編排框架
- **LangChain**: LLM 應用開發框架
- **Pydantic**: 資料驗證和序列化
- **Uvicorn**: ASGI 伺服器

### 前端技術棧
- **Vue.js**: 響應式前端框架
- **Vuetify**: Material Design 組件庫
- **Vite**: 前端建置工具

### AI 整合
- **多模型支援**: 同時支援多種 LLM 提供商
- **動態提示管理**: 可配置的提示範本系統
- **記憶體管理**: LangGraph 檢查點機制

## 許可證

本專案採用 MIT 授權條款 - 詳細內容請參閱 LICENSE 檔案。
