from typing import TypedDict


class CSState(TypedDict, total=False):
    uuid: str
    source_path: str
    errors: list

    targetPath: str
    language: str
    project_info: str  # 用戶提供的系統描述
    cs_original_path: str
    cs_json_path: str
    cs_csv_path: str
    developers_output_path: str
    chunks: list
    csResponses: list
    developers: list

    file_dependency_lists: list

    dependency_patterns: list
    file_extensions: list
    keywords: list
    comment_syntax: dict  # Comment syntax for the language
    all_files: list
    function_mapping: dict
    dependency_mapping: dict
    file_dependencies: list
    comments_collection: str  # Path to collected comments file
    preprocess_json_path: str
    json_language_analysis_path: str


class SAState(TypedDict, total=False):
    uuid: str
    source_path: str
    cs_original_path: str
    cs_json_path: str
    errors: list

    intermediate_data: list
    project_name: str | None
    project_info: str  # 用戶提供的系統描述
    analysis_results: dict

    # 系統背景與目標
    system_background_objectives: dict
    # 利害關係人分析
    stakeholder_analysis: dict
    # 現行流程與痛點
    current_processes_pain_points: dict
    # 目標流程與功能需求
    target_processes_functional_requirements: dict
    # 使用者介面與操作流程
    user_interface_operation_flow: dict
    # 非功能性需求
    non_functional_requirements: dict
    # 系統架構規劃與平台系統建置說明
    system_architecture_platform_build: dict
    # 資料庫設計
    database_design: dict
    # 流程圖與畫面原型
    flowcharts_screen_prototypes: dict
    # 風險與限制
    risks_limitations: dict

    project_recommendations: dict
    conclusion: dict
    # Final document
    sa_document: list  # JSON format document with chapters
    sa_output_path: str
    sa_sensitive: list


class BPState(TypedDict, total=False):
    uuid: str
    source_path: str
    project_info: str  # 用戶提供的系統描述
    targetPath: str
    cs_original_path: str
    cs_json_path: str
    cs_csv_path: str
    developers_output_path: str
    blueprint_json_path: str
    manifest_data: dict
    organized_modules: list
    blueprint_data: list
    chunks: list
    csResponses: list
    errors: list
    developers: list
    bp_sensitive: list


class CTState(TypedDict, total=False):
    uuid: str
    source_path: str
    targetPath: str
    cs_original_path: str
    cs_json_path: str
    cs_json_path_updated: str
    cs_csv_path: str
    project_info: str

    developers_output_path: str
    blueprint_json_path: str
    blueprint_json_path_updated: str
    blueprint_data: dict
    chunks: list
    csResponses: list
    errors: list
    developers: list
    ct_sensitive: list


class MTState(TypedDict, total=False):
    uuid: str
    source_path: str
    targetPath: str
    cs_original_path: str
    cs_json_path: str
    cs_csv_path: str

    developers_output_path: str
    merged: str

    blueprint_json_path: str
    blueprint_json_path_updated: str
    chunks: list
    csResponses: list
    errors: list
    devlopers: list


class VerificationState(TypedDict, total=False):
    uuid: str
    developers_output_path: str
    error_report_path: str
    fixed_code_path: str
    blueprint_json_path: str
    verification_sensitive: list
