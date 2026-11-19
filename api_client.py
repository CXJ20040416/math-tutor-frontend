"""成员3 后端 HTTP 接口的接入位（预留，当前默认不启用）。

现状：成员3 给出的地址是 `http://127.0.0.1:8000/...`（本机回环），
外部（含 Streamlit Cloud）不可达，故前端当前**全部走本地规则**，
由 service.py 直接调用成员1 的纯函数。本文件只做「接口契约 + 开关」，
不改变现有行为，供成员3 交付可达地址后一处切换。

接入步骤（成员3 提供可达地址后）：
1. 在 Streamlit Cloud → App settings → Secrets 增加：
   BACKEND_BASE_URL = "https://<成员3 的公网/局域网可达地址>"
   （本地开发也可用环境变量 BACKEND_BASE_URL 注入）
2. 调用 is_remote_enabled() 判断是否已配置；已配置时前端改走 HTTP，
   未配置时保持本地规则，两端行为可对照，便于成员5 做前后端一致性核对。
3. 需与成员3 对齐的接口（对应《页面与接口对应表.md》第二节）：
   - GET  /api/status/{student_id}/{topic}   学习状态与掌握判断
   - POST /api/sessions                      开启作答会话
   - POST /api/sessions/{session_id}/events  追加 submit/hint/solution 事件
   - POST /api/sessions/{session_id}/close   关闭会话并生成 Evidence
   - GET  /api/review/{student_id}/plan      复测计划与下次日期
   - POST /api/review/{student_id}/finish    复测结算
   - POST /api/uploads                       图片原图与转录存取
   - GET  /openapi.json                      接口契约（成员3 提供后据此定稿）

字段口径：见《页面与接口对应表.md》第四节；接口若用不同命名，
由成员3 给出映射，不在前端另起字段。
"""
import os

ENV_KEY = "BACKEND_BASE_URL"


def base_url() -> str:
    """读取后端根地址：优先 Streamlit Secrets，其次环境变量；未配置返回空串。"""
    try:
        import streamlit as st

        value = st.secrets.get(ENV_KEY, "")
    except Exception:  # 非 Streamlit 运行环境或未配置 secrets
        value = ""
    return (value or os.environ.get(ENV_KEY, "")).rstrip("/")


def is_remote_enabled() -> bool:
    """后端地址已配置时返回 True。当前线上部署未配置，故为 False（走本地规则）。"""
    return bool(base_url())


def endpoint(path: str) -> str:
    """拼出完整接口地址，便于成员3 交付后逐条核对。"""
    root = base_url()
    if not root:
        raise RuntimeError(
            f"{ENV_KEY} 未配置：前端仍走本地规则。"
            "请成员3 提供可外部访问的地址后写入 Streamlit Secrets。"
        )
    return f"{root}/{path.lstrip('/')}"
