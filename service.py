"""成员2 前端服务层（原型）。

职责：把成员1 的纯规则模块接到 Streamlit 页面。原型阶段会话/证据/计划存于
st.session_state（内存），不做数据库持久化——持久化、鉴权、并发与事务由成员3 实现。
判分为演示级宽松匹配，真实数学批改/OCR 由成员4 提供。
"""
import re
import sys
from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "data"))

from learning_rules import (  # noqa: E402
    Policy, QuestionSession, Event, Outcome, Kind,
    append_event, summarize, assess, prepare_validation,
    start_schedule, finish_review, review_result, learning_status,
)
import questions as Q  # noqa: E402

TZ = ZoneInfo("Asia/Hong_Kong")
ROUND_ID = "student-demo-round-001"


def make_policy() -> Policy:
    return Policy(required_families=(Q.FAMILY,),
                  questions_per_family=Q.QUESTIONS_PER_FAMILY)


def judge(answer_text: str, answer_value: int) -> Outcome:
    """演示级判分：提取作答中的数字与参考答案比较。非真实数学批改。"""
    if answer_text is None or not answer_text.strip():
        return Outcome.NO_ATTEMPT
    nums = re.findall(r"-?\d+(?:\.\d+)?", answer_text)
    if not nums:
        return Outcome.WRONG
    try:
        return Outcome.CORRECT if abs(float(nums[-1]) - answer_value) < 1e-9 else Outcome.WRONG
    except ValueError:
        return Outcome.WRONG


def _now(state_day: date, seq: int) -> datetime:
    return datetime.combine(state_day, datetime.min.time(), TZ) + timedelta(seconds=seq)


def new_session(question: dict, kind: Kind, *, recent_lesson: bool = False,
                seen_before: bool = False) -> QuestionSession:
    return QuestionSession(
        session_id=f"{question['question_id']}-{datetime.now(TZ).strftime('%H%M%S%f')}",
        topic_id=Q.TOPIC_ID,
        question_id=question["question_id"],
        question_version="demo-v1",
        family_id=question["family_id"],
        difficulty=Q.DIFFICULTY,
        kind=kind,
        seen_before=seen_before,
        recent_lesson=recent_lesson,
        recent_similar_example=False,
        source="system",
        assessment_form=question.get("assessment_form", "solve"),
        learning_round=ROUND_ID,
        target_is_whole_question=True,  # 演示兼容整题映射；真实题须按 rubric 拆分
    )


def prepare_validation_session(question: dict) -> QuestionSession:
    session = new_session(question, Kind.VALIDATION)
    return prepare_validation(session, teaching_closed=True, background_verified=True)


def add_submit(session: QuestionSession, event_seq: int, state_day: date,
               answer: str, outcome: Outcome) -> QuestionSession:
    target = None if outcome == Outcome.NO_ATTEMPT else outcome
    event = Event(
        event_id=f"{session.session_id}-s{event_seq}",
        at=_now(state_day, event_seq),
        action="submit", answer=answer, outcome=outcome, target_outcome=target,
    )
    return append_event(session, event)


def add_hint(session: QuestionSession, event_seq: int, state_day: date, level: int) -> QuestionSession:
    return append_event(session, Event(
        event_id=f"{session.session_id}-h{level}", at=_now(state_day, event_seq),
        action="hint", level=level))


def add_solution(session: QuestionSession, event_seq: int, state_day: date) -> QuestionSession:
    return append_event(session, Event(
        event_id=f"{session.session_id}-sol{event_seq}", at=_now(state_day, event_seq),
        action="solution"))


def close_to_evidence(session: QuestionSession) :
    return summarize(session)


def assess_view(evidence_list, schedule, policy: Policy):
    return assess(Q.TOPIC_ID, tuple(evidence_list), schedule, policy, learning_round=ROUND_ID)


def start_review_schedule(topic_id: str, on: date, policy: Policy):
    return start_schedule(topic_id, on, policy)


def finish_current(schedule, task_id, on: date, items, policy: Policy,
                   end_round: bool = False, technical_issue: bool = False):
    return finish_review(schedule, task_id, on, tuple(items), policy,
                         end_round=end_round, technical_issue=technical_issue)


def review_outcome(items, policy: Policy, *, end_round: bool = False,
                   technical_issue: bool = False) -> str:
    """预判本轮复测结果：passed / failed / pending。不推进计划、不写库。"""
    return review_result(tuple(items), Q.TOPIC_ID, policy,
                         end_round=end_round, technical_issue=technical_issue)


def placeholder_evidence(question: dict, kind: Kind):
    """未作答题的占位证据（空会话汇总），供主动结束/异常时凑齐题数校验。

    首答为空，规则层据此判 pending，不形成有效失败证据。
    """
    sess = new_session(question, kind)
    return summarize(sess)


def entry_status(entry: str, lesson_finished: bool, has_submission: bool) -> dict:
    return learning_status(entry, lesson_finished, has_submission)
