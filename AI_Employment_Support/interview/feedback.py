import os
import json
from openai import AsyncOpenAI

client = AsyncOpenAI(api_key=os.getenv("OPENAI"))

FEEDBACK_SYSTEM_PROMPT = """
너는 면접 코치다.
지원자의 전체 면접 질문/답변 기록을 바탕으로 종합 피드백을 작성한다.

매우 중요한 규칙:
- 피드백은 반드시 실제 답변 내용에 근거해야 한다.
- 추상적인 고정 문구를 반복하지 마라.
- 강점은 실제 답변에서 드러난 행동, 설명 방식, 구조, 표현을 근거로 작성하라.
- 보완점은 실제 부족했던 답변 방식, 회피, 단답형, 구체성 부족 등을 근거로 작성하라.
- 답변 스타일 패턴(예: 짧은 답변, 회피형 답변, 구조 부족, 본인 역할 설명 부족)을 함께 분석해 반영하라.
- weaknesses와 improvements에는 반복적으로 나타난 답변 스타일 문제를 우선적으로 반영하라.
- "왜 그것이 좋은지", "면접에서 어떻게 보이는지"까지 설명하라.
- 답변이 전반적으로 부실했다면 억지로 강점을 만들지 마라.
- 반드시 JSON 객체만 반환하라.

반환 형식:
{
  "overall_summary": "...",
  "strengths": ["...", "..."],
  "weaknesses": ["...", "..."],
  "improvements": ["...", "..."],
  "sample_answer_tip": "..."
}
"""

BAD_PATTERNS = [
    "모르겠습니다", "잘 모르겠습니다", "모르겠어요", "아니요", "없습니다",
    "패스", "기억이 안 납니다", "기억 안 납니다", "음", "네", "몰라",
    "하기 싫", "취업하기 싫", "잘 모르겠", "딱히 없습니다"
]
def detect_answer_style(question: str, answer: str) -> list[str]:
    tags = []

    q = (question or "").strip()
    a = (answer or "").strip()

    if len(a) < 15:
        tags.append("short")

    if any(p in a for p in BAD_PATTERNS):
        tags.append("avoidant")

    vague_words = ["열심히", "잘", "최대한", "많이", "적절히", "그냥", "대체로"]
    if any(word in a for word in vague_words):
        tags.append("vague")

    role_keywords = ["제가", "저는", "제 역할", "담당", "맡", "기여", "주도", "구현"]
    if not any(word in a for word in role_keywords):
        tags.append("no_role_detail")

    result_keywords = ["결과", "성과", "개선", "증가", "감소", "%", "효율", "완료", "달성"]
    if not any(word in a for word in result_keywords):
        tags.append("no_result_detail")

    job_keywords = ["직무", "역량", "업무", "기술", "협업", "프로젝트", "문제", "경험"]
    if "지원" in q or "직무" in q or "역량" in q:
        if not any(word in a for word in job_keywords):
            tags.append("weak_job_relevance")

    structure_keywords = ["상황", "문제", "행동", "결과", "당시", "이후", "그래서"]
    if len(a) >= 20 and not any(word in a for word in structure_keywords):
        tags.append("weak_structure")

    return list(dict.fromkeys(tags))

def is_bad_answer(text: str) -> bool:
    t = (text or "").strip()
    if len(t) < 10:
        return True
    return any(p in t for p in BAD_PATTERNS)


def summarize_history_for_feedback(history: list[dict]) -> dict:
    total = len(history)
    bad_answers = []
    good_answers = []
    retried = 0
    style_counter = {}

    for item in history:
        answer = item.get("answer", "").strip()
        question = item.get("question", "").strip()
        was_retried = item.get("was_retried", False)

        if was_retried:
            retried += 1

        style_tags = detect_answer_style(question, answer)

        for tag in style_tags:
            style_counter[tag] = style_counter.get(tag, 0) + 1

        record = {
            "question": question,
            "answer": answer[:300],
            "style_tags": style_tags
        }

        if is_bad_answer(answer):
            bad_answers.append(record)
        else:
            good_answers.append(record)

    dominant_styles = sorted(
        style_counter.items(),
        key=lambda x: x[1],
        reverse=True
    )

    return {
        "total_questions": total,
        "good_count": len(good_answers),
        "bad_count": len(bad_answers),
        "retry_count": retried,
        "good_examples": good_answers[:3],
        "bad_examples": bad_answers[:3],
        "style_counter": style_counter,
        "dominant_styles": dominant_styles[:5],
    }


def build_dynamic_tip(history: list[dict], bad_examples: list[dict], good_examples: list[dict]) -> str:
    if bad_examples:
        target = bad_examples[0]
        answer = target.get("answer", "").strip()
        question = target.get("question", "").strip()

        if len(answer) < 10:
            return (
                f"예를 들어 '{question}' 같은 질문에서는 단답형으로 끝내기보다, "
                "'제가 맡았던 상황은 무엇이었고, 어떤 행동을 했으며, 결과가 어땠는지'를 2~3문장으로 이어서 설명해보세요."
            )

        if "모르" in answer or "없" in answer or "패스" in answer:
            return (
                f"'{question}'에 바로 답하기 어렵더라도 "
                "'직접 경험은 부족하지만 비슷한 사례를 기준으로 말씀드리겠습니다'처럼 연결해서 답하면 훨씬 자연스럽습니다."
            )

        return (
            f"'{question}'에 대한 답변은 조금 더 구체적으로 보완할 수 있습니다. "
            "상황, 본인의 역할, 실제 행동, 결과를 순서대로 나눠 설명해보세요."
        )

    if good_examples:
        target = good_examples[0]
        question = target.get("question", "").strip()
        return (
            f"좋았던 답변 방식은 계속 유지하세요. 특히 '{question}'처럼 경험을 설명할 때는 "
            "앞으로도 상황-행동-결과 구조를 유지하면 더 안정적으로 답변할 수 있습니다."
        )

    if history:
        return (
            "답변이 막힐 때는 먼저 결론을 한 문장으로 말하고, "
            "그다음 상황-행동-결과 순서로 풀어가면 훨씬 설득력 있게 들립니다."
        )

    return "답변은 결론부터 짧게 말한 뒤, 상황-행동-결과 순서로 정리하면 전달력이 좋아집니다."


async def generate_final_feedback(
    company: str | None,
    role: str | None,
    job_posting: str,
    resume: str,
    history: list[dict],
) -> dict:
    analysis = summarize_history_for_feedback(history)

    history_text = "\n".join(
        [
            f"Q{i+1}. {item['question']}\nA{i+1}. {item['answer']}"
            for i, item in enumerate(history)
        ]
    )

    analysis_text = f"""
[답변 분석 요약]
- 전체 질문 수: {analysis['total_questions']}
- 비교적 성실한 답변 수: {analysis['good_count']}
- 부실하거나 회피성 답변 수: {analysis['bad_count']}
- 보충 요청이 있었던 질문 수: {analysis['retry_count']}

[비교적 성실한 답변 예시]
{json.dumps(analysis['good_examples'], ensure_ascii=False, indent=2)}

[부실하거나 회피성 답변 예시]
{json.dumps(analysis['bad_examples'], ensure_ascii=False, indent=2)}
"""

    prompt = f"""
[회사]
{company or "미지정"}

[직무]
{role or "미지정"}

[채용공고]
{job_posting}

[자소서]
{resume}

[면접 전체 기록]
{history_text}

{analysis_text}

위 내용을 바탕으로 종합 피드백을 작성하라.

중요:
1. 강점은 실제 답변에서 드러난 표현 방식, 구조, 경험 설명, 직무 연결 시도를 근거로 작성할 것
2. 보완점은 실제 부족했던 답변을 근거로 작성할 것
3. 답변 내용이 전반적으로 부실하면 강점을 비워도 된다
4. "이 답변이 왜 좋았는지", "면접에서 어떤 인상을 주는지"를 포함할 것
5. 반드시 JSON 객체만 반환할 것
"""

    try:
        response = await client.chat.completions.create(
            model="gpt-5",
            messages=[
                {"role": "system", "content": FEEDBACK_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=0.8,
            response_format={"type": "json_object"},
        )

        content = response.choices[0].message.content
        print("DEBUG feedback raw content:", content)

        parsed = json.loads(content)

        required_keys = [
            "overall_summary",
            "strengths",
            "weaknesses",
            "improvements",
            "sample_answer_tip",
        ]
        for key in required_keys:
            if key not in parsed:
                raise ValueError(f"Missing key: {key}")

        return {
            "overall_summary": str(parsed["overall_summary"]),
            "strengths": list(parsed["strengths"])[:3],
            "weaknesses": list(parsed["weaknesses"])[:3],
            "improvements": list(parsed["improvements"])[:3],
            "sample_answer_tip": str(parsed["sample_answer_tip"]),
        }

    except Exception as e:
        print("DEBUG generate_final_feedback ERROR:", type(e).__name__, str(e))

        strengths = []
        weaknesses = []
        improvements = []

        dominant_style_names = [name for name, _count in analysis["dominant_styles"]]

        if "short" in dominant_style_names:
            weaknesses.append("전체적으로 답변 길이가 짧아 면접관이 경험과 역량을 충분히 파악하기 어려운 구간이 있었습니다.")

        if "avoidant" in dominant_style_names:
            weaknesses.append("일부 질문에서는 회피성 답변이 나타나 면접 태도와 준비도 측면에서 아쉬운 인상을 줄 수 있습니다.")

        if "no_role_detail" in dominant_style_names:
            weaknesses.append("여러 답변에서 본인이 맡은 역할과 기여가 분명하게 드러나지 않았습니다.")

        if "no_result_detail" in dominant_style_names:
            weaknesses.append("답변에서 결과나 성과 설명이 부족해 설득력이 약해질 수 있었습니다.")

        if "weak_structure" in dominant_style_names:
            improvements.append("답변을 상황-역할-행동-결과 순서로 나눠 말하면 구조가 훨씬 또렷해집니다.")

        if "no_role_detail" in dominant_style_names:
            improvements.append("각 답변에서 '제가 맡은 역할은 무엇이었는지'를 한 문장으로 먼저 분명히 말해보세요.")

        if "no_result_detail" in dominant_style_names:
            improvements.append("답변 마지막에는 결과, 변화, 배운 점 중 하나를 꼭 덧붙여보세요.")

        if "avoidant" in dominant_style_names:
            improvements.append("모르는 질문도 바로 포기하지 말고, 유사 경험이나 대처 방향으로 연결해 답변해보세요.")
            
        if analysis["good_examples"]:
            ex = analysis["good_examples"][0]
            strengths.append(
                f"'{ex['answer'][:80]}'처럼 자신의 경험을 이어서 설명하려는 답변은 면접관이 지원자의 실제 경험을 파악하는 데 도움이 됩니다."
            )

        if len(analysis["good_examples"]) >= 2:
            ex = analysis["good_examples"][1]
            strengths.append(
                f"'{ex['answer'][:80]}'와 같이 직무와 연결되는 내용을 언급한 점은 직무 적합성을 보여주는 데 긍정적으로 작용할 수 있습니다."
            )

        if analysis["bad_examples"]:
            ex = analysis["bad_examples"][0]
            weaknesses.append(
                f"'{ex['answer'][:50]}'와 같은 답변은 질문 의도에 대한 충분한 설명이 부족해 면접관이 역량을 판단하기 어렵게 만들 수 있습니다."
            )

        if len(analysis["bad_examples"]) >= 2:
            ex = analysis["bad_examples"][1]
            weaknesses.append(
                f"'{ex['answer'][:50]}'처럼 짧거나 회피적인 답변은 성실성과 준비도 측면에서 아쉬운 인상을 줄 수 있습니다."
            )

        if analysis["retry_count"] > 0:
            weaknesses.append(
                f"총 {analysis['retry_count']}개의 질문에서 보충 답변이 필요했습니다. 이는 답변의 구체성과 구조를 더 보완해야 한다는 신호입니다."
            )

        improvements.append("질문마다 상황, 본인의 역할, 실제 행동, 결과 순서로 답변을 구성해보세요.")
        improvements.append("모르는 질문도 단답형으로 끝내지 말고, 유사 경험이나 대처 방향을 설명해보세요.")
        improvements.append("답변에서 직무와 연결되는 포인트를 한 문장이라도 분명히 언급해보세요.")

        if not strengths and analysis["bad_count"] >= max(1, int(analysis["total_questions"] * 0.8)):
            overall_summary = (
                f"총 {analysis['total_questions']}개의 질문 중 대부분에서 구체적인 경험 설명이 부족했습니다. "
                "전반적으로 답변의 성실성과 구조가 부족해 면접관이 지원자의 역량을 충분히 파악하기 어려운 상태였습니다."
            )
        else:
            overall_summary = (
                f"총 {analysis['total_questions']}개의 질문에 대한 답변을 바탕으로 보면, "
                "일부 답변에서는 경험을 설명하려는 흐름이 있었지만 답변 간 편차가 있었고 구체성이 부족한 구간도 확인되었습니다."
            )

        sample_tip = build_dynamic_tip(
            history=history,
            bad_examples=analysis["bad_examples"],
            good_examples=analysis["good_examples"],
        )

        return {
            "overall_summary": overall_summary,
            "strengths": strengths[:3],
            "weaknesses": weaknesses[:3],
            "improvements": improvements[:3],
            "sample_answer_tip": sample_tip,
        }