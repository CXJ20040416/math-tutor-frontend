"""演示题库（模拟数据，非正式审核题库）。

说明：
- 本文件仅用于成员2前端原型演示，题目与标准答案均为演示数据，
  不代表正式题库；正式题库由成员4配合提供，成员5审核标准答案与目标步骤。
- 知识点：正系数单括号方程 / 基础难度；必测族 positive_single，每族 2 题。
- answer 为参考答案数值；原型判分只做宽松数字匹配，不做真实数学批改（成员4）。
"""

TOPIC_ID = "positive_single_equation"
TOPIC_NAME = "正系数单括号方程 · 基础"
DIFFICULTY = "basic"
FAMILY = "positive_single"
QUESTIONS_PER_FAMILY = 2

# kind: example / practice / diagnostic / validation / variant / transfer / review
QUESTIONS = [
    {
        "question_id": "ex-01",
        "kind": "example",
        "assessment_form": "solve",
        "family_id": FAMILY,
        "stem": "例题：解方程 2(x+3)=14。",
        "solution": "去括号：2x+6=14；移项：2x=8；解得 x=4。",
        "answer_value": 4,
        "target_note": "目标步骤：正确去括号并求解。",
    },
    {
        "question_id": "pr-01",
        "kind": "practice",
        "assessment_form": "solve",
        "family_id": FAMILY,
        "stem": "即时练习：解方程 3(x+1)=12。",
        "solution": "去括号：3x+3=12；移项：3x=9；解得 x=3。",
        "answer_value": 3,
        "target_note": "目标步骤：正确去括号并求解。",
    },
    {
        "question_id": "diag-01",
        "kind": "diagnostic",
        "assessment_form": "solve",
        "family_id": FAMILY,
        "stem": "诊断题：解方程 2(x+3)=14。",
        "solution": "去括号：2x+6=14；移项：2x=8；解得 x=4。",
        "answer_value": 4,
        "target_note": "目标步骤：正确去括号并求解。",
    },
    {
        "question_id": "val-01",
        "kind": "validation",
        "assessment_form": "solve",
        "family_id": FAMILY,
        "stem": "独立验证 1：解方程 3(x+2)=18。",
        "solution": "去括号：3x+6=18；移项：3x=12；解得 x=4。",
        "answer_value": 4,
        "target_note": "目标步骤：正确去括号并求解。",
    },
    {
        "question_id": "val-02",
        "kind": "validation",
        "assessment_form": "solve",
        "family_id": FAMILY,
        "stem": "独立验证 2：解方程 4(x+1)=20。",
        "solution": "去括号：4x+4=20；移项：4x=16；解得 x=4。",
        "answer_value": 4,
        "target_note": "目标步骤：正确去括号并求解。",
    },
    {
        "question_id": "trans-01",
        "kind": "transfer",
        "assessment_form": "solve",
        "family_id": FAMILY,
        "stem": "情境迁移：三个相同的文具包，每包有一本本子和一支 2 元的笔，共 18 元，求一本本子多少元。",
        "solution": "设本子 x 元：3(x+2)=18；解得 x=4。",
        "answer_value": 4,
        "target_note": "目标步骤：正确列式并求解。",
    },
]

# 复测题：每轮两道新求解题（演示池，数字轮换；真实抽题由题库/后端提供）
# 六档复测共需 12 道未见新题，另备失败重启备用，本池共 16 道。
REVIEW_POOL = [
    {"question_id": "rv-101", "family_id": FAMILY, "stem": "复测题 A：解方程 3(x+2)=18。", "solution": "3x+6=18；3x=12；x=4。", "answer_value": 4},
    {"question_id": "rv-102", "family_id": FAMILY, "stem": "复测题 B：解方程 2(x+4)=16。", "solution": "2x+8=16；2x=8；x=4。", "answer_value": 4},
    {"question_id": "rv-103", "family_id": FAMILY, "stem": "复测题 C：解方程 4(x+2)=24。", "solution": "4x+8=24；4x=16；x=4。", "answer_value": 4},
    {"question_id": "rv-104", "family_id": FAMILY, "stem": "复测题 D：解方程 2(x+5)=18。", "solution": "2x+10=18；2x=8；x=4。", "answer_value": 4},
    {"question_id": "rv-105", "family_id": FAMILY, "stem": "复测题 E：解方程 4(x+1)=20。", "solution": "4x+4=20；4x=16；x=4。", "answer_value": 4},
    {"question_id": "rv-106", "family_id": FAMILY, "stem": "复测题 F：解方程 2(x+3)=14。", "solution": "2x+6=14；2x=8；x=4。", "answer_value": 4},
    {"question_id": "rv-107", "family_id": FAMILY, "stem": "复测题 G：解方程 3(x+1)=15。", "solution": "3x+3=15；3x=12；x=4。", "answer_value": 4},
    {"question_id": "rv-108", "family_id": FAMILY, "stem": "复测题 H：解方程 5(x+2)=25。", "solution": "5x+10=25；5x=15；x=3。", "answer_value": 3},
    {"question_id": "rv-109", "family_id": FAMILY, "stem": "复测题 I：解方程 2(x+6)=16。", "solution": "2x+12=16；2x=4；x=2。", "answer_value": 2},
    {"question_id": "rv-110", "family_id": FAMILY, "stem": "复测题 J：解方程 6(x+1)=30。", "solution": "6x+6=30；6x=24；x=4。", "answer_value": 4},
    {"question_id": "rv-111", "family_id": FAMILY, "stem": "复测题 K：解方程 3(x+3)=21。", "solution": "3x+9=21；3x=12；x=4。", "answer_value": 4},
    {"question_id": "rv-112", "family_id": FAMILY, "stem": "复测题 L：解方程 2(x+2)=12。", "solution": "2x+4=12；2x=8；x=4。", "answer_value": 4},
    {"question_id": "rv-113", "family_id": FAMILY, "stem": "复测题 M：解方程 4(x+3)=28。", "solution": "4x+12=28；4x=16；x=4。", "answer_value": 4},
    {"question_id": "rv-114", "family_id": FAMILY, "stem": "复测题 N：解方程 5(x+1)=20。", "solution": "5x+5=20；5x=15；x=3。", "answer_value": 3},
    {"question_id": "rv-115", "family_id": FAMILY, "stem": "复测题 O：解方程 2(x+7)=16。", "solution": "2x+14=16；2x=2；x=1。", "answer_value": 1},
    {"question_id": "rv-116", "family_id": FAMILY, "stem": "复测题 P：解方程 3(x+4)=24。", "solution": "3x+12=24；3x=12；x=4。", "answer_value": 4},
]

HINTS = {
    1: "方向提示：先观察括号外的系数，考虑先去括号。",
    2: "方法提示：用分配律把括号展开，再把常数项移到等号另一边。",
    3: "关键步骤：ax + b = c 形式中，先求 ax = c - b，再求 x。",
}
