import os
import json
from openai import AsyncOpenAI

client = AsyncOpenAI(api_key=os.getenv("OPENAI"))

QUESTION_SYSTEM_PROMPT = """
너는 실제 기업 면접관처럼 행동하는 AI 면접 질문 생성기다.

규칙:
- 질문은 반드시 채용공고와 자소서 내용을 직접 반영해야 한다.
- 일반적인 면접 질문만 반복하지 말고, 공고의 직무/주요업무/자격요건/우대사항을 반영하라.
- 자소서에 언급된 프로젝트, 기술, 경험을 반드시 반영하라.
- 총 5개의 질문을 생성한다.
- 5개 질문 모두 서로 다른 목적을 가져야 한다.
- 최소 3개 질문은 특정 기술, 프로젝트, 업무, 경험을 직접 언급해야 한다.
- 아래와 같은 지나치게 일반적인 질문은 금지한다:
  "자기소개 해주세요", "지원동기를 말씀해주세요", "협업 경험을 말씀해주세요",
  "문제 해결 경험을 말씀해주세요", "가장 인상 깊은 프로젝트는 무엇인가요"
- 첫 질문만 비교적 일반적이어도 되지만, 2~5번은 반드시 구체적이어야 한다.
- 반드시 JSON 배열만 반환한다.
"""

GENERIC_PATTERNS = [
    "자기소개",
    "지원동기",
    "협업 경험",
    "문제 해결 경험",
    "인상 깊었던 프로젝트",
    "장단점",
]

def is_too_generic(question: str) -> bool:
    return any(pattern in question for pattern in GENERIC_PATTERNS)


async def generate_interview_questions(
    job_posting: str,
    resume: str,
    company: str | None = None,
    role: str | None = None,
) -> list[str]:
    prompt = f"""
[회사]
{company or "미지정"}

[직무]
{role or "미지정"}

[채용공고]
{job_posting}

[자소서]
{resume}

위 정보를 바탕으로 모의면접 질문 5개를 생성하라.

조건:
1. 1번 질문은 지원동기 또는 자기소개 기반 질문 가능
2. 2~5번 질문은 반드시 채용공고 또는 자소서의 구체적인 내용이 직접 반영되어야 함
3. 최소 2개 질문은 채용공고의 주요업무/자격요건/우대사항을 직접 반영할 것
4. 최소 2개 질문은 자소서에 언급된 프로젝트/경험/기술을 직접 반영할 것
5. 추상적이고 반복적인 일반 면접 질문은 금지
6. 반드시 JSON 배열만 반환
"""

    try:
        response = await client.chat.completions.create(
            model="gpt-5",
            messages=[
                {"role": "system", "content": QUESTION_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=0.9,
        )

        content = response.choices[0].message.content.strip()
        print("DEBUG question raw content:", content)

        questions = json.loads(content)
        questions = [str(q).strip() for q in questions if str(q).strip()]
        print("DEBUG parsed questions:", questions)

        if len(questions) >= 5:
            generic_count = sum(is_too_generic(q) for q in questions[1:])  # 2~5번만 검사
            if generic_count <= 1:
                return questions[:5]

        print("DEBUG question quality check failed, using tailored fallback")

    except Exception as e:
        print("DEBUG generate_interview_questions ERROR:", type(e).__name__, str(e))

    return [
        f"{company or '지원한 회사'}의 {role or '해당 직무'}에 지원한 이유를 말씀해주세요.",
        f"{company or '해당 기업'}의 공고에서 요구하는 주요 역량 중 본인이 가장 자신 있는 부분은 무엇인가요?",
        f"자소서에서 언급한 경험 중 {role or '이 직무'}와 가장 직접적으로 연결되는 사례를 설명해주세요.",
        "이전 프로젝트에서 본인이 직접 의사결정을 내렸던 경험과 그 근거를 말씀해주세요.",
        "이해관계자 조율이나 협업 과정에서 어려움을 해결한 구체적인 사례를 말씀해주세요.",
    ]