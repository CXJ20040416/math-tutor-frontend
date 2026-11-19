"""成员2 可运行前端原型（Streamlit）。

接入成员1 规则模块 backend/learning_rules.py；会话/证据/计划存浏览器内存会话状态，
不做数据库持久化（成员3）；判分为演示级宽松匹配，真实批改/OCR 待成员4；题库为演示数据，正式题库由成员4配合、成员5审核。
启动：streamlit run app.py
"""
import sys
import time
from datetime import date
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "data"))

import service as S  # noqa: E402
import questions as Q  # noqa: E402
from learning_rules import Outcome, Kind  # noqa: E402

st.set_page_config(page_title="数学学习助手 · 成员2前端原型 v0.4", layout="wide")


def init_state():
    ss = st.session_state
    if ss.get("inited"):
        return
    ss.policy = S.make_policy()
    ss.evidence = []
    ss.schedule = None
    ss.stage = "home"
    ss.session = None
    ss.question = None
    ss.seq = 0
    ss.review_items = []
    ss.used_q = set()
    ss.today = date(2026, 11, 12)
    ss.lesson_finished = False
    ss.entry = None
    ss.log = []
    ss.photo_state = {}
    ss.submission_meta = {}
    ss.inited = True


def log(msg: str):
    st.session_state.log.append(msg)


def assessment():
    return S.assess_view(st.session_state.evidence, st.session_state.schedule, st.session_state.policy)


def find_question(qid: str):
    return next((q for q in Q.QUESTIONS if q["question_id"] == qid), None)


# ---------- 进度与回顾推导 ----------
KIND_LABELS = {
    Kind.PRACTICE: "即时练习", Kind.DIAGNOSTIC: "诊断", Kind.VALIDATION: "独立验证",
    Kind.TRANSFER: "情境迁移", Kind.REVIEW: "复测", Kind.EXAMPLE: "例题",
}


def done_kinds():
    return {e.kind for e in st.session_state.evidence}


def progress_counts():
    ev = st.session_state.evidence
    correct = sum(1 for e in ev if e.final_outcome == Outcome.CORRECT)
    return len(ev), correct


def is_wrong_review(ev) -> bool:
    """错题口径：首答出错 / 最终出错 / 提示（含答案）后才作对。"""
    if ev.first_outcome == Outcome.WRONG:
        return True
    if ev.final_outcome == Outcome.WRONG:
        return True
    if ev.max_hint and ev.final_outcome == Outcome.CORRECT:
        return True
    if ev.solution_seen and ev.final_outcome == Outcome.CORRECT:
        return True
    return False


def _ev_row(ev):
    q = find_question(ev.question_id)
    stem = q["stem"] if q else ev.question_id
    first = ev.first_outcome.value if ev.first_outcome else "—"
    final = ev.final_outcome.value if ev.final_outcome else "—"
    hint = ev.max_hint or "无"
    independent = "是" if ev.independent else "否"
    return f"- **{KIND_LABELS.get(ev.kind, ev.kind.value)}**｜{stem}\n  - 首答：{first} ｜ 最终：{final} ｜ 提示：{hint} ｜ 独立：{independent} ｜ 看过答案：{'是' if ev.solution_seen else '否'}"


def history_view(only_wrong: bool):
    evs = st.session_state.evidence
    if only_wrong:
        evs = [e for e in evs if is_wrong_review(e)]
        st.subheader("错题回顾")
    else:
        st.subheader("整体回顾")
    if not evs:
        st.info("还没有已完成的题目。")
        return
    st.caption(f"共 {len(evs)} 题")
    for ev in evs:
        st.markdown(_ev_row(ev))



# ---------- 照片转录前端状态（OCR 待成员4，此处仅前端状态流转） ----------
def empty_photo_state() -> dict:
    return {"file_name": None, "image_bytes": None, "raw_ocr": "", "confirmed": "",
            "edited": False, "confirmed_done": False, "edit_source": None}


def reset_question_widgets(qid: str):
    """结束/保存本题后清理作答、转录、照片控件状态，保证同题重开不带旧输入。"""
    ss = st.session_state
    for k in (f"answer_{qid}", f"ocr_confirm_{qid}", f"photo_{qid}"):
        ss.pop(k, None)
    ss.photo_state.pop(qid, None)


def photo_block(question: dict):
    ss = st.session_state
    qid = question["question_id"]
    state = ss.photo_state.setdefault(qid, empty_photo_state())

    up = st.file_uploader("上传手写解答照片", type=["png", "jpg", "jpeg"],
                          key=f"photo_{qid}")
    if up is not None and state["file_name"] is None:
        state["file_name"] = up.name
        state["image_bytes"] = up.getvalue()
        # 模拟 OCR 原始转录；真实识别结果由成员4 返回
        state["raw_ocr"] = f"[模拟 OCR] {question['stem'].rstrip('。')}，学生手写待识别"
        state["confirmed"] = state["raw_ocr"]
        state["edited"] = False
        state["confirmed_done"] = False
        state["edit_source"] = "raw"
        log(f"[照片] 已上传 {up.name}，生成模拟原始转录")

    if state["file_name"] is not None:
        st.markdown("**照片与转录核对（前端状态演示，OCR 待成员4）**")
        if state["image_bytes"] is not None:
            st.image(state["image_bytes"], caption=f"原图：{state['file_name']}", width=220)
        else:
            st.write(f"· 原图：{state['file_name']}（受控存储待成员3）")
        st.write(f"· 原始转录 raw_ocr：{state['raw_ocr'] or '—'}")

        current = st.text_input("逐行转录核对 / 修正后文本", value=state["confirmed"],
                                key=f"ocr_confirm_{qid}")
        if current != state["confirmed"]:
            state["confirmed"] = current
            state["edited"] = current.strip() != state["raw_ocr"].strip()
            state["edit_source"] = "manual_edit"
            if state["confirmed_done"]:
                # 确认后再编辑 → 撤销确认，需重新确认
                state["confirmed_done"] = False
                log("[照片] 转录被再次修改，已撤销上次确认，需重新确认")

        c1, c2 = st.columns(2)
        with c1:
            if st.button("确认转录并用于作答", key=f"ocr_ok_{qid}",
                         disabled=state["confirmed_done"] or not state["confirmed"].strip()):
                state["confirmed_done"] = True
                state["edit_source"] = "manual_edit" if state["edited"] else "raw"
                log("[照片] 学生确认转录；原始转录/确认版本/修改来源已留存")
        with c2:
            if st.button("重新拍摄（补拍）", key=f"ocr_retake_{qid}"):
                # 清掉上传/转录/作答控件状态，避免旧图随重跑再次载入
                for k in (f"photo_{qid}", f"ocr_confirm_{qid}", f"answer_{qid}"):
                    ss.pop(k, None)
                ss.photo_state[qid] = empty_photo_state()
                log("[照片] 已放弃当前照片与转录，可重新拍摄")
                st.rerun()

        if state["confirmed_done"]:
            st.success(f"转录已确认{'（含手动修正）' if state['edited'] else '（与原始转录一致）'}，作答来源：照片。")
        else:
            st.info("请核对原始转录，修正后确认；未确认前照片不能作为有效提交（可改用文字作答）。")


# ---------- 作答区 ----------
def resolve_submission(question: dict):
    """判定本次提交方式与文本。

    返回 (mode, answer_text, photo_state)：
    - mode="photo"：已有已核对并确认的转录，提交使用确认版本；
    - mode="text"：未确认照片或未上传，提交使用文字框内容。
    """
    ss = st.session_state
    qid = question["question_id"]
    photo = ss.photo_state.get(qid)
    text_val = (ss.get(f"answer_{qid}") or "").strip()
    if photo and photo["confirmed_done"] and photo["confirmed"].strip():
        return "photo", photo["confirmed"].strip(), photo
    return "text", text_val, photo


def _current_evidence():
    ss = st.session_state
    return S.close_to_evidence(ss.session) if ss.session else None


def answer_block(question: dict, kind_label: str, *, allow_hint: bool = True,
                 on_next_label: str = "下一题", on_next=None, show_metrics: bool = True,
                 next_on_submit: bool = False):
    ss = st.session_state
    qid = question["question_id"]
    st.markdown(f"**{question['stem']}**")
    st.caption(question.get("target_note", "目标步骤：正确求解并给出结果。"))

    photo_block(question)

    photo_now = ss.photo_state.get(qid)
    if photo_now and photo_now["confirmed_done"] and photo_now["confirmed"].strip():
        st.caption("当前作答方式：照片（已确认转录，提交将使用确认版本）")
    else:
        st.caption("当前作答方式：文字（上传并确认转录后可切换为照片作答）")
        if photo_now and photo_now["file_name"]:
            st.warning("照片尚未确认，本次按文字作答；如需照片作答请先确认转录。")

    ev = _current_evidence()
    submitted = ev is not None and ev.first_outcome is not None
    hint_levels = sorted(e.level for e in ss.session.events if e.action == "hint") if ss.session else []

    # 对错标记：输入框下方以 ✓/✗ 与颜色提示
    if submitted:
        if ev.final_outcome == Outcome.CORRECT:
            st.success("✓ 回答正确")
        elif ev.final_outcome == Outcome.WRONG:
            st.error("✗ 回答错误，可请求提示或修改后再提交")
        elif ev.final_outcome == Outcome.NO_ATTEMPT:
            st.info("○ 已标记暂时不会")

    # 表单：输入框 + 提交按钮，支持回车提交
    with st.form(key=f"form_{qid}", clear_on_submit=False):
        answer = st.text_input("输入你的解答（文字作答）", key=f"answer_{qid}")
        form_submit = st.form_submit_button("提交作答")

    if form_submit:
        mode, answer_text, photo = resolve_submission(question)
        outcome = S.judge(answer_text, question["answer_value"])
        if mode == "photo":
            source_note = "含手动修正" if photo["edited"] else "与原始转录一致"
            meta = {"mode": "photo", "edited": photo["edited"],
                    "edit_source": photo["edit_source"],
                    "raw_ocr": photo["raw_ocr"], "confirmed": photo["confirmed"]}
            log(f"[{kind_label}] 照片作答提交（确认版本，{source_note}），整题判定：{outcome.value}")
        else:
            meta = {"mode": "text", "edited": False, "edit_source": None,
                    "raw_ocr": None, "confirmed": None}
            log(f"[{kind_label}] 文字作答提交，整题判定：{outcome.value}")
        ss.seq += 1
        ss.session = S.add_submit(ss.session, ss.seq, ss.today, answer_text, outcome)
        ss.submission_meta.setdefault(qid, []).append(meta)
        st.rerun()

    # 已展示提示：从会话事件重建，刷新/交互后仍可读，不重复记录帮助
    for lvl in hint_levels:
        st.info(f"提示 {lvl}/3：{Q.HINTS[lvl]}")

    # 操作按钮：请求提示 / 暂时不会 / 查看完整答案（答案需至少请求过一次提示后出现）
    c1, c2, c3 = st.columns(3)
    with c1:
        if allow_hint:
            next_level = (max(hint_levels) + 1) if hint_levels else 1
            if next_level <= 3:
                if st.button(f"请求 {next_level} 级提示", key=f"btn_hint_{qid}"):
                    ss.seq += 1
                    ss.session = S.add_hint(ss.session, ss.seq, ss.today, next_level)
                    log(f"[{kind_label}] 请求 {next_level} 级提示")
                    st.rerun()
            else:
                st.warning("已展示全部三级提示。")
    with c2:
        if st.button("暂时不会", key=f"btn_noattempt_{qid}"):
            ss.seq += 1
            ss.session = S.add_submit(ss.session, ss.seq, ss.today, "", Outcome.NO_ATTEMPT)
            log(f"[{kind_label}] 选择暂时不会（no_attempt）")
            st.rerun()
    with c3:
        if hint_levels:
            if st.button("查看完整答案", key=f"btn_solution_{qid}"):
                ss.seq += 1
                ss.session = S.add_solution(ss.session, ss.seq, ss.today)
                st.rerun()

    # 完整答案：若事件已记录查看过，则持续展示（从事件重建）
    if ss.session and any(e.action == "solution" for e in ss.session.events):
        st.warning(f"完整答案：{question['solution']}")

    # 提交后出现继续按钮：默认仅答对；next_on_submit 时只要已提交即出现
    if on_next is not None and submitted and (next_on_submit or ev.final_outcome == Outcome.CORRECT):
        if st.button(on_next_label, key=f"btn_next_{qid}", type="primary"):
            on_next()

    if submitted and show_metrics:
        st.divider()
        cols = st.columns(4)
        cols[0].metric("整题首答", ev.first_outcome.value if ev.first_outcome else "—")
        cols[1].metric("整题最终", ev.final_outcome.value if ev.final_outcome else "—")
        cols[2].metric("最高提示等级", ev.max_hint or "无")
        cols[3].metric("是否独立完成", "是" if ev.independent else "否")
        if ev.first_target is not None or ev.final_target is not None:
            st.write(f"目标步骤：首答 {ev.first_target.value if ev.first_target else '—'} ｜ 最终 {ev.final_target.value if ev.final_target else '—'}")
        history = [e for e in ss.session.events if e.action == "submit"]
        st.caption(f"作答历史：共 {len(history)} 次提交（首答保留，不被覆盖）；查看过完整答案：{'是' if ev.solution_seen else '否'}")


def leave_to_home(message: str):
    """离开当前练习：提示 N 秒后返回初始页面，并在首页同步进度。"""
    ss = st.session_state
    st.success(message)
    st.info("3 秒后返回初始页面…")
    time.sleep(3)
    ss.stage = "home"
    st.rerun()


def finish_current(kind_label: str, next_stage: str):
    ss = st.session_state
    if not ss.session:
        st.warning("当前没有进行中的作答。")
        return
    ev = S.close_to_evidence(ss.session)
    ss.evidence.append(ev)
    ss.used_q.add(ss.question["question_id"])
    log(f"[{kind_label}] 保存证据：{ev.question_id} / 独立={ev.independent}")
    reset_question_widgets(ss.question["question_id"])
    ss.session = None
    ss.question = None
    if kind_label == "独立验证":
        remaining = [q for q in Q.QUESTIONS if q["kind"] == "validation"
                     and q["question_id"] not in ss.used_q]
        next_stage = "validation" if remaining else next_stage
    ss.stage = next_stage
    st.rerun()


# ---------- 主流程 ----------
init_state()
ss = st.session_state

# 顶部标题 + 更多菜单（⋮）：后台状态、回顾、日志均收纳于此
top_l, top_r = st.columns([8, 2])
with top_l:
    st.title("中学生数学学习助手 · 成员2 前端原型 v0.4")
with top_r:
    with st.popover("⋮ 更多"):
        if st.button("学习状态总览", key="menu_status"):
            ss.stage = "status"
            st.rerun()
        if st.button("整体回顾", key="menu_history"):
            ss.stage = "history"
            st.rerun()
        if st.button("错题回顾", key="menu_wrong"):
            ss.stage = "history_wrong"
            st.rerun()
        st.divider()
        st.caption("操作日志（事件留痕）")
        for line in ss.log[-30:]:
            st.write(f"· {line}")
        st.divider()
        if st.button("重置演示", key="menu_reset"):
            for k in list(ss.keys()):
                del ss[k]
            st.rerun()

st.caption(
    "演示模式：匿名访客，无登录鉴权（成员3 接入身份）。规则计算接通成员1模块；题库、判分、OCR 为演示/模拟。"
    "作答记录仅存当前浏览器内存，刷新页面会重置（数据库持久化待成员3）。"
)

# 侧栏：仅保留轻量学习进度，后台判断信息收进 ⋮ 菜单
with st.sidebar:
    st.header("学习进度")
    total, correct = progress_counts()
    st.metric("已完成题目", f"{total}")
    st.write(f"· 其中答对：{correct} 题")
    done = done_kinds()
    for kind, label in KIND_LABELS.items():
        if kind in done:
            st.write(f"· {label}：已完成")
    if ss.schedule:
        st.write(f"复测轮次：{ss.schedule.cycle} ｜ 下次：{ss.schedule.due_on or '本轮已完成'}")

# 主区按阶段渲染
if ss.stage == "home":
    total, correct = progress_counts()
    st.subheader("选择学习入口")
    st.write(f"目前进度：已完成 **{total}** 题，答对 **{correct}** 题。")
    col1, col2 = st.columns(2)
    with col1:
        st.info("**预习 / 自学**：先看概念与例题，可即时练习，稍后再测。")
        if st.button("进入预习自学", key="entry_self"):
            ss.entry = "self_study"
            ss.stage = "example"
            st.rerun()
    with col2:
        st.info("**已学过直接测试**：直接做诊断题，首答与帮助全程留痕。")
        if st.button("直接开始测试", key="entry_direct"):
            ss.entry = "direct_test"
            ss.stage = "diagnostic"
            st.rerun()
    if total > 0:
        if st.button("查看已学过的知识（回顾）", key="go_history"):
            ss.stage = "history"
            st.rerun()
    st.caption("“稍后测试”：自学进度单独保存，不新增掌握证据（对应 learning_status）。")

elif ss.stage == "status":
    a = assessment()
    st.subheader("学习状态总览")
    st.metric("掌握程度", a.level.value)
    for r in a.reasons:
        st.write(f"· {r}")
    if a.families:
        st.markdown("| 题目族 | 状态 | 独立题数 | 要求题数 |")
        st.markdown("|---|---|---|---|")
        for f in a.families:
            st.markdown(f"| {f.family_id} | {f.status} | {f.independent_count} | {f.required_count} |")
    if ss.schedule:
        st.write(f"复测轮次：{ss.schedule.cycle} ｜ 阶段：{ss.schedule.stage} ｜ 下次：{ss.schedule.due_on or '本轮已完成'}")
        st.write(f"复测记录条数：{len(ss.schedule.records)}")
    st.write(f"有效证据条数：{len(ss.evidence)}")
    if st.button("返回首页", key="back_status"):
        ss.stage = "home"
        st.rerun()

elif ss.stage == "history":
    history_view(False)
    if st.button("返回首页", key="back_history"):
        ss.stage = "home"
        st.rerun()

elif ss.stage == "history_wrong":
    history_view(True)
    if st.button("返回首页", key="back_wrong"):
        ss.stage = "home"
        st.rerun()

elif ss.stage == "example":
    q = find_question("ex-01")
    st.subheader("讲解与例题")
    st.markdown(f"**{q['stem']}**")
    st.success(q["solution"])
    ss.lesson_finished = True
    c1, c2, c3 = st.columns(3)
    with c1:
        if st.button("做即时练习", key="go_practice"):
            ss.stage = "practice"
            st.rerun()
    with c2:
        if st.button("稍后测试", key="go_later"):
            leave_to_home("已保存学习进度，待测评；不新增掌握证据。")
    with c3:
        if st.button("跳过练习，开始独立验证", key="go_val_from_example"):
            ss.stage = "validation"
            st.rerun()

elif ss.stage == "practice":
    q = find_question("pr-01")
    if ss.session is None:
        ss.question = q
        ss.session = S.new_session(q, Kind.PRACTICE, recent_lesson=True)
    st.subheader("即时练习（不直接更新掌握等级）")

    def leave_practice():
        if ss.session:
            ev = S.close_to_evidence(ss.session)
            ss.evidence.append(ev)
            ss.used_q.add(q["question_id"])
            log(f"[即时练习] 保存证据：{ev.question_id} / 独立={ev.independent}")
            reset_question_widgets(q["question_id"])
            ss.session = None
            ss.question = None
        leave_to_home("练习进度已保存，3 秒后返回初始页面。")

    answer_block(q, "即时练习", on_next_label="暂时离开", on_next=leave_practice)
    if st.button("暂时离开", key="finish_practice"):
        leave_practice()

elif ss.stage == "diagnostic":
    q = find_question("diag-01")
    if ss.session is None:
        ss.question = q
        ss.session = S.new_session(q, Kind.DIAGNOSTIC)
    st.subheader("诊断题")

    def go_diag_result():
        finish_current("诊断", "after_assess")

    answer_block(q, "诊断", on_next_label="查看诊断结果", on_next=go_diag_result)
    if st.button("提交诊断结果", key="finish_diag"):
        go_diag_result()

elif ss.stage == "validation":
    pending = [q for q in Q.QUESTIONS if q["kind"] == "validation" and q["question_id"] not in ss.used_q]
    if not pending:
        ss.stage = "after_assess"
        st.rerun()
    q = pending[0]
    ss.question = q
    if ss.session is None:
        try:
            ss.session = S.prepare_validation_session(q)
            log(f"[独立验证] prepare_validation 通过：{q['question_id']}")
        except ValueError as e:
            st.error(f"独立验证准备被拒绝：{e}")
    st.subheader("独立验证（目标难度 · 必测族新题）")

    def go_val_next():
        finish_current("独立验证", "after_assess")

    answer_block(q, "独立验证", on_next_label="下一题", on_next=go_val_next)
    if st.button("完成验证题", key="finish_val"):
        go_val_next()

elif ss.stage == "after_assess":
    a = assessment()
    today_done = ss.schedule is not None and ss.schedule.complete
    st.subheader("当前掌握判断")
    st.metric("等级", a.level.value)
    for r in a.reasons:
        st.write(f"· {r}")
    if a.families:
        st.markdown("| 题目族 | 状态 | 独立题数 | 要求题数 |")
        st.markdown("|---|---|---|---|")
        for f in a.families:
            st.markdown(f"| {f.family_id} | {f.status} | {f.independent_count} | {f.required_count} |")

    if today_done:
        st.success("今日学习已完成")
        if st.button("返回主界面", key="back_home_done"):
            ss.stage = "home"
            st.rerun()
    else:
        if a.schedule_eligible and ss.schedule is None:
            if st.button("达标：创建次日复测计划", key="start_sched"):
                ss.schedule = S.start_review_schedule(Q.TOPIC_ID, ss.today, ss.policy)
                log("达到独立应用门槛，已创建首次复测计划（次日到期）")
                st.rerun()
        if ss.schedule is not None and not ss.schedule.complete:
            st.button("进入复测", key="go_review", on_click=lambda: setattr(ss, "stage", "review"))
        if any(e.kind == Kind.TRANSFER for e in ss.evidence):
            st.success("已具备情境迁移证据。")
        else:
            trans = find_question("trans-01")
            if trans and trans["question_id"] not in ss.used_q:
                if st.button("做情境迁移题（迁移证据单独记录，不代替族覆盖）", key="go_transfer"):
                    ss.stage = "transfer"
                    st.rerun()

        # 下一步：已完成的选项消去
        done = done_kinds()
        remaining_val = [q for q in Q.QUESTIONS if q["kind"] == "validation"
                         and q["question_id"] not in ss.used_q]
        show_practice = Kind.PRACTICE not in done
        show_diag = Kind.DIAGNOSTIC not in done
        if show_practice or show_diag or remaining_val:
            st.divider()
            st.markdown("**下一步**")
            col_a, col_b = st.columns(2)
            with col_a:
                if show_practice:
                    if st.button("补学：再做即时练习", key="go_practice2"):
                        ss.stage = "practice"
                        st.rerun()
            with col_b:
                if remaining_val:
                    if st.button("做新题独立验证", key="go_val2"):
                        ss.stage = "validation"
                        st.rerun()
            if show_diag:
                if st.button("重做诊断题", key="back_diag"):
                    ss.stage = "diagnostic"
                    st.rerun()

elif ss.stage == "transfer":
    q = find_question("trans-01")
    if ss.session is None:
        ss.question = q
        ss.session = S.new_session(q, Kind.TRANSFER)
    st.subheader("情境迁移")

    def go_transfer_done():
        finish_current("迁移", "after_assess")

    answer_block(q, "迁移", on_next_label="下一题", on_next=go_transfer_done)
    if st.button("完成迁移题", key="finish_transfer"):
        go_transfer_done()

elif ss.stage == "review":
    if ss.schedule is None:
        st.warning("尚无复测计划，请先在掌握判断页达到独立应用门槛。")
    else:
        sched = ss.schedule
        st.subheader("正式复测")
        st.write(f"轮次 {sched.cycle} ｜ 阶段 {sched.stage} ｜ 到期日 {sched.due_on}")
        if ss.today < sched.due_on:
            st.info(f"尚未到期（演示日期 {ss.today}）。原型可模拟推进到到期日。")
            if st.button("模拟推进到到期日（演示）", key="jump_due"):
                ss.today = sched.due_on
                st.rerun()
        else:
            pool = [q for q in Q.REVIEW_POOL if q["question_id"] not in ss.used_q]
            if len(ss.review_items) < ss.policy.review_questions:
                qi = len(ss.review_items)
                q = pool[qi] if qi < len(pool) else None
                if q is None:
                    st.warning("演示题库新题已耗尽；真实系统应提示补充题库（成员4/5）。")
                else:
                    if ss.session is None:
                        ss.question = q
                        ss.session = S.new_session(q, Kind.REVIEW)
                    remaining = ss.policy.review_questions - len(ss.review_items)
                    st.caption(f"本轮复测进度：{len(ss.review_items)}/{ss.policy.review_questions}（剩余 {remaining} 题）")

                    def save_review_q():
                        ev = S.close_to_evidence(ss.session)
                        ss.review_items.append(ev)
                        ss.used_q.add(q["question_id"])
                        reset_question_widgets(q["question_id"])
                        ss.session = None
                        ss.question = None
                        st.rerun()

                    answer_block(q, "复测", allow_hint=True, show_metrics=False,
                                 next_on_submit=True,
                                 on_next_label="保存本题并继续下一道", on_next=save_review_q)

            # 结算 / 结束 / 异常：默认收起，不在作答页直接展示
            with st.expander("本轮结算 / 结束与异常"):
                end_round = st.checkbox("学生主动结束本轮（已有明确失败）", key="end_round")
                tech = st.checkbox("技术异常，暂缓结算", key="tech_issue")

                trial = list(ss.review_items)
                missing = ss.policy.review_questions - len(trial)
                placeholder_qs = pool[len(ss.review_items):len(ss.review_items) + missing]
                if len(placeholder_qs) < missing:
                    st.warning("演示题库不足，无法补齐本轮题数；请先补充复测题。")
                else:
                    for pq in placeholder_qs:
                        trial.append(S.placeholder_evidence(pq, Kind.REVIEW))
                    try:
                        outcome = S.review_outcome(trial, ss.policy,
                                                   end_round=end_round, technical_issue=tech)
                    except ValueError as e:
                        st.error(f"复测校验被规则拒绝：{e}")
                        outcome = "pending"
                    outcome_label = {"pending": "待处理 / 暂缓", "passed": "通过", "failed": "失败"}[outcome]
                    st.caption(f"当前预判：{outcome_label}（已保存 {len(ss.review_items)} 题，占位未交 {missing} 题）")
                    if st.button("提交本轮复测结果", key="finish_review_round"):
                        if outcome == "pending":
                            log("[复测] pending：保留当前任务与已存证据，暂不发布到已结算列表")
                            st.warning("本轮暂缓结算：计划与当前题目证据已保留，未计入已结算记录；恢复后可同任务重试，仅结算一次。")
                        else:
                            try:
                                ss.schedule = S.finish_current(
                                    ss.schedule, ss.schedule.task_id, ss.today,
                                    trial, ss.policy,
                                    end_round=end_round, technical_issue=tech)
                                ss.evidence.extend(ss.review_items)  # 占位证据不进入全局已结算列表
                                log(f"[复测] 结算 {outcome}；下一次 {ss.schedule.due_on}")
                                ss.review_items = []
                                ss.stage = "after_assess"
                                st.rerun()
                            except ValueError as e:
                                st.error(f"复测结算被规则拒绝：{e}")
