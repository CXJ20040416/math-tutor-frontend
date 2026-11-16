"""学习循环规则 v1.3.1。纯 Python，无模型/网页/数据库依赖。
调用方负责鉴权、持久化、事务与题库审核。所有 date 使用 Asia/Hong_Kong 本地日期。
"""
from dataclasses import dataclass, replace
from datetime import date, datetime, timedelta
from enum import Enum
from typing import Optional


class Outcome(str, Enum):
    CORRECT = 'correct'
    WRONG = 'wrong'
    NO_ATTEMPT = 'no_attempt'
    PENDING = 'pending'


class Kind(str, Enum):
    EXAMPLE = 'example'
    PRACTICE = 'practice'
    VALIDATION = 'validation'
    DIAGNOSTIC = 'diagnostic'
    VARIANT = 'variant'
    TRANSFER = 'transfer'
    REVIEW = 'review'


class Mastery(str, Enum):
    UNKNOWN = '掌握程度待确定'
    SUPPORT = '需要支持'
    DEVELOPING = '初步理解'
    INDEPENDENT = '独立应用'
    STABLE = '短期保持已验证'


@dataclass(frozen=True)
class Policy:
    intervals: tuple[int, ...] = (1, 2, 4, 7, 15, 30)
    required_families: tuple[str, ...] = ()  # 必须由知识点/难度配置，不默认凑三个族
    questions_per_family: int = 1
    review_questions: int = 2
    stable_passes: int = 2
    stable_min_days: int = 3

    def __post_init__(self):
        numbers = (*self.intervals, self.questions_per_family, self.review_questions,
                   self.stable_passes, self.stable_min_days)
        if any(type(n) is not int or n < 1 for n in numbers):
            raise ValueError('间隔与题数门槛必须为正整数，不接受布尔值或小数')
        if any(not isinstance(f, str) or not f.strip() for f in self.required_families):
            raise ValueError('题目族 ID 必须为非空字符串')
        if len(set(self.required_families)) != len(self.required_families) or any(not f for f in self.required_families):
            raise ValueError('必测族必须非空且不重复')
        if not self.intervals or any(i <= 0 for i in self.intervals):
            raise ValueError('复测间隔必须为正整数')
        if min(self.questions_per_family, self.review_questions,
               self.stable_passes, self.stable_min_days) < 1:
            raise ValueError('门槛必须为正整数')


DEFAULT_POLICY = Policy()


@dataclass(frozen=True)
class Event:
    """追加写入的题内事件。submit 必须是已核对内容的实际提交。
    OCR 识别、转录编辑在外部暂存，未确认时不得创建 submit。
    """
    event_id: str
    at: datetime
    action: str  # submit / hint / solution / lesson
    answer: Optional[str] = None
    outcome: Optional[Outcome] = None
    level: Optional[int] = None
    target_outcome: Optional[Outcome] = None  # 目标关键步骤，未确认不能推断

    def __post_init__(self):
        if not self.event_id or self.at.tzinfo is None or self.at.utcoffset() is None:
            raise ValueError('必须有事件 ID 和带时区时间')
        if self.action not in {'submit', 'hint', 'solution', 'lesson'}:
            raise ValueError('未知事件类型')
        if self.action == 'submit':
            if not isinstance(self.outcome, Outcome):
                raise ValueError('整题判定必须使用 Outcome 枚举')
            if self.outcome == Outcome.NO_ATTEMPT and self.target_outcome not in (None, Outcome.NO_ATTEMPT, Outcome.PENDING):
                raise ValueError('未作答不能同时声称目标步骤正确或错误')
            if self.outcome is None or self.outcome == Outcome.PENDING:
                raise ValueError('待确认判分应保留草稿，不进入有效事件流')
            if self.outcome != Outcome.NO_ATTEMPT and self.answer is None:
                raise ValueError('实际提交需要答案文本或确认后的转录')
        elif self.outcome is not None or self.answer is not None:
            raise ValueError('帮助事件不能携带作答')
        if self.target_outcome is not None and not isinstance(self.target_outcome, Outcome):
            raise ValueError('目标判定必须使用 Outcome 枚举')
        if self.action != 'submit' and self.target_outcome is not None:
            raise ValueError('只有作答事件可以有目标步骤判定')
        if self.action == 'hint':
            if self.level not in (1, 2, 3):
                raise ValueError('提示等级必须为 1、2、3')
        elif self.level is not None:
            raise ValueError('只有提示事件有等级')


@dataclass(frozen=True)
class QuestionSession:
    session_id: str
    topic_id: str
    question_id: str
    question_version: str
    family_id: str  # 数学结构与解题要求，曝光历史另行检查
    difficulty: str
    kind: Kind
    seen_before: bool = False
    recent_lesson: bool = False
    recent_similar_example: bool = False
    source: str = 'system'  # external 只能作为辅助证据
    events: tuple[Event, ...] = ()
    assessment_form: str = 'solve'  # solve / error_check / completion
    learning_round: str = 'default'
    target_is_whole_question: bool = False  # 仅经题库审核的单目标题允许整题映射
    validation_ready: bool = False


def append_event(session: QuestionSession, event: Event) -> QuestionSession:
    """同 ID 同内容重复请求幂等；同 ID 异内容、乱序、跳级提示拒绝。"""
    for previous in session.events:
        if previous.event_id == event.event_id:
            if previous != event:
                raise ValueError('事件 ID 冲突')
            return session
    if session.events and event.at < session.events[-1].at:
        raise ValueError('事件必须按时间追加')
    if event.action == 'hint':
        highest = max((e.level for e in session.events if e.action == 'hint'), default=0)
        if event.level > highest + 1:
            raise ValueError('提示应逐级展示')
    return replace(session, events=session.events + (event,))


@dataclass(frozen=True)
class Evidence:
    session_id: str
    topic_id: str
    question_id: str
    family_id: str
    difficulty: str
    kind: Kind
    first_outcome: Optional[Outcome]
    final_outcome: Optional[Outcome]
    max_hint: int
    solution_seen: bool
    help_before_first: bool
    independent: bool
    comparable: bool
    at: Optional[datetime]
    assessment_form: str = 'solve'
    learning_round: str = 'default'
    first_target: Optional[Outcome] = None
    final_target: Optional[Outcome] = None


def summarize(session: QuestionSession) -> Evidence:
    submissions = [e for e in session.events if e.action == 'submit']
    first = submissions[0] if submissions else None
    last = submissions[-1] if submissions else None
    first_index = next((i for i, e in enumerate(session.events) if e.action == 'submit'), len(session.events))
    before = any(e.action in {'hint', 'solution', 'lesson'} for e in session.events[:first_index])
    comparable = session.source == 'system' and not session.seen_before
    def target(event):
        if event is None:
            return None
        value = event.target_outcome
        if value is None and session.target_is_whole_question:
            value = event.outcome
        return None if value == Outcome.PENDING else value
    first_target, final_target = target(first), target(last)
    independent = bool(first and first_target == Outcome.CORRECT and not before
                       and (session.kind != Kind.VALIDATION or session.validation_ready)
                       and not session.recent_lesson and not session.recent_similar_example
                       and comparable)
    return Evidence(session.session_id, session.topic_id, session.question_id,
                    session.family_id, session.difficulty, session.kind,
                    first.outcome if first else None, last.outcome if last else None,
                    max((e.level for e in session.events if e.action == 'hint'), default=0),
                    any(e.action == 'solution' for e in session.events), before,
                    independent, comparable, first.at if first else None,
                    session.assessment_form, session.learning_round, first_target, final_target)


@dataclass(frozen=True)
class ReviewRecord:
    task_id: str
    cycle: int
    stage: int
    due_on: date
    completed_on: date
    passed: bool
    evidence_ids: tuple[str, ...]
    ended_early: bool = False


@dataclass(frozen=True)
class Schedule:
    topic_id: str
    cycle: int
    stage: int  # 0..5 等待对应间隔的复测；6 表示完成
    started_on: date
    due_on: Optional[date]
    records: tuple[ReviewRecord, ...] = ()

    @property
    def task_id(self) -> str:
        return f'{self.topic_id}:c{self.cycle}:s{self.stage}'

    @property
    def complete(self) -> bool:
        return self.due_on is None


def start_schedule(topic_id: str, on: date, policy: Policy = DEFAULT_POLICY) -> Schedule:
    return Schedule(topic_id, 1, 0, on, on + timedelta(days=policy.intervals[0]))


def review_result(items: tuple[Evidence, ...], topic_id: str,
                  policy: Policy = DEFAULT_POLICY, *, end_round: bool = False,
                  technical_issue: bool = False) -> str:
    """一轮复测需固定数量、同难度、新题。pending 不改变计划；完整轮才判成败。"""
    if len(items) != policy.review_questions:
        raise ValueError('复测题数不符合配置')
    if any(e.topic_id != topic_id or e.kind != Kind.REVIEW for e in items):
        raise ValueError('知识点或测评类型不匹配')
    if any(e.assessment_form != 'solve' for e in items):
        raise ValueError('正式复测采用求解形式')
    if len({e.learning_round for e in items}) != 1:
        raise ValueError('同一复测任务不能混合学习轮次')
    if len({e.question_id for e in items}) != len(items):
        raise ValueError('复测不能重复使用同一道题')
    if policy.required_families and any(e.family_id not in policy.required_families for e in items):
        raise ValueError('复测题不属于配置的必测族')
    if len({e.difficulty for e in items}) != 1 or not all(e.comparable for e in items):
        raise ValueError('复测要求同难度且未见过的系统题')
    if technical_issue:
        return 'pending'
    known = [e for e in items if e.first_outcome is not None and e.first_target is not None]
    if end_round and any(not e.independent for e in known):
        return 'failed'
    if len(known) != len(items):
        return 'pending'
    return 'passed' if all(e.independent for e in items) else 'failed'


def finish_review(schedule: Schedule, task_id: str, on: date,
                  items: tuple[Evidence, ...], policy: Policy = DEFAULT_POLICY, *,
                  end_round: bool = False, technical_issue: bool = False) -> Schedule:
    # 重放已处理任务不重复推进；调用者仍须使用数据库事务/版本锁。
    previous = next((r for r in schedule.records if r.task_id == task_id), None)
    if previous:
        result = review_result(items, schedule.topic_id, policy, end_round=end_round, technical_issue=technical_issue)
        if (previous.ended_early != end_round or previous.completed_on != on or previous.evidence_ids != tuple(e.session_id for e in items)
                or result == 'pending' or previous.passed != (result == 'passed')):
            raise ValueError('已完成任务不可覆盖')
        return schedule
    if schedule.complete or task_id != schedule.task_id:
        raise ValueError('复测任务已过期或不匹配')
    if on < schedule.due_on:
        raise ValueError('提前练习不能推进延迟复测')
    result = review_result(items, schedule.topic_id, policy, end_round=end_round, technical_issue=technical_issue)
    if result == 'pending':
        return schedule
    used = {sid for record in schedule.records for sid in record.evidence_ids}
    if any(e.session_id in used for e in items):
        raise ValueError('同一证据不能用于多轮复测')
    from zoneinfo import ZoneInfo
    if any(e.at.astimezone(ZoneInfo('Asia/Hong_Kong')).date() != on for e in items if e.at is not None):
        raise ValueError('复测作答应属于本次实际完成日期')
    passed = result == 'passed'
    record = ReviewRecord(task_id, schedule.cycle, schedule.stage,
                          schedule.due_on, on, passed, tuple(e.session_id for e in items), end_round)
    history = schedule.records + (record,)
    if not passed:
        return Schedule(schedule.topic_id, schedule.cycle + 1, 0, on,
                        on + timedelta(days=policy.intervals[0]), history)
    stage = schedule.stage + 1
    due = on + timedelta(days=policy.intervals[stage]) if stage < len(policy.intervals) else None
    return replace(schedule, stage=stage, due_on=due, records=history)


@dataclass(frozen=True)
class FamilyAssessment:
    family_id: str
    status: str  # passed / insufficient / support
    evidence_ids: tuple[str, ...]
    independent_count: int
    required_count: int


@dataclass(frozen=True)
class Assessment:
    level: Mastery
    reasons: tuple[str, ...]
    schedule_eligible: bool
    families: tuple[FamilyAssessment, ...] = ()


def assess(topic_id: str, items: tuple[Evidence, ...], schedule: Optional[Schedule] = None,
           policy: Policy = DEFAULT_POLICY, learning_round: str = 'default') -> Assessment:
    """按单知识点、单难度传入证据。规则门槛是项目初版设计，非科学诊断量表。"""
    if schedule is not None and schedule.topic_id != topic_id:
        raise ValueError('复测计划知识点不匹配')
    if not policy.required_families:
        return Assessment(Mastery.UNKNOWN, ('尚未配置该知识点与难度的必测题目族',), False)
    valid = [e for e in items if e.topic_id == topic_id and e.first_outcome is not None
             and e.first_target is not None and e.comparable and e.learning_round == learning_round
             and e.kind in {Kind.DIAGNOSTIC, Kind.VALIDATION, Kind.REVIEW}
             and e.assessment_form == 'solve' and e.family_id in policy.required_families]
    if len({e.difficulty for e in valid}) > 1:
        raise ValueError('不同难度必须分别评估')
    if len({e.session_id for e in valid}) != len(valid):
        raise ValueError('重复证据')
    valid.sort(key=lambda e: e.at)
    if not valid:
        return Assessment(Mastery.UNKNOWN, ('尚无已确认的有效目标步骤证据',), False,
                          tuple(FamilyAssessment(f, 'insufficient', (), 0, policy.questions_per_family)
                                for f in policy.required_families))
    # 各必测族分别取最近 N 道不同题；失败族重测不清空其他族。
    recent = []
    passed = []
    families = []
    for family in policy.required_families:
        unique = {e.question_id: e for e in valid if e.family_id == family}
        window = sorted(unique.values(), key=lambda e: e.at)[-policy.questions_per_family:]
        recent.extend(window)
        if len(window) == policy.questions_per_family and all(e.independent for e in window):
            passed.append(family)
        status = 'passed' if family in passed else (
            'support' if any(not e.independent for e in window) else 'insufficient')
        families.append(FamilyAssessment(family, status, tuple(e.session_id for e in window),
                                        sum(e.independent for e in window), policy.questions_per_family))
    families = tuple(families)
    latest = max(recent, key=lambda e: e.at)
    eligible = len(passed) == len(policy.required_families)
    missing = [f for f in policy.required_families if f not in passed]
    reasons = (f'必测族已通过 {len(passed)}/{len(policy.required_families)}',
               '待验证题目族：' + ('、'.join(missing) if missing else '无'))
    if eligible:
        consecutive = []
        if schedule:
            for record in reversed(schedule.records):
                if not record.passed:
                    break
                consecutive.append(record)
        span = ((max(r.completed_on for r in consecutive) - schedule.started_on).days
                if consecutive else 0)
        # 迁移须来自本轮起点之后，旧轮迁移不能支撑失败重启后的稳定判断。
        from zoneinfo import ZoneInfo
        transfer = any(e.kind == Kind.TRANSFER and e.assessment_form == 'solve'
                       and e.at is not None and e.independent and
                       (not schedule or e.at.astimezone(ZoneInfo('Asia/Hong_Kong')).date() >= schedule.started_on)
                       for e in items if e.topic_id == topic_id and e.learning_round == learning_round
                       and e.difficulty == latest.difficulty and e.comparable)
        if len(consecutive) >= policy.stable_passes and span >= policy.stable_min_days and transfer:
            return Assessment(Mastery.STABLE, reasons + (f'连续通过 {len(consecutive)} 次延迟复测，且有情境迁移证据',), True, families)
        return Assessment(Mastery.INDEPENDENT, reasons + ('延迟保持或迁移证据尚未达到短期保持门槛',), True, families)
    if any(f.status == 'support' for f in families):
        return Assessment(Mastery.SUPPORT, reasons + ('存在尚未通过的题目族，需针对性补学或订正',), False, families)
    return Assessment(Mastery.DEVELOPING, reasons + ('已有独立证据，仍需补足必测族或题数',), False, families)


def prepare_validation(session: QuestionSession, *, teaching_closed: bool,
                       background_verified: bool) -> QuestionSession:
    """由服务端调用；新题已选好且背景已核验。不得清除既有帮助或近期影响。"""
    if session.kind != Kind.VALIDATION or session.events:
        raise ValueError('仅可准备尚未作答的新独立验证会话')
    if not teaching_closed or not background_verified:
        raise ValueError('须结束教学环节并完成背景核验')
    if (session.seen_before or session.recent_lesson or session.recent_similar_example
            or session.source != 'system'):
        raise ValueError('当前题目或帮助背景不适合独立验证')
    return replace(session, validation_ready=True)


def learning_status(entry: str, lesson_finished: bool, has_submission: bool) -> dict[str, str]:
    if entry not in {'self_study', 'direct_test'}:
        raise ValueError('未知入口')
    return {
        'learning': '已完成讲解' if lesson_finished else ('学习中' if entry == 'self_study' else '未开始'),
        'assessment': '已有测评记录' if has_submission else '待测评',
    }
