import os
import re
import json
import asyncio
from openai import AsyncOpenAI
from dotenv import load_dotenv

load_dotenv()

client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))


# ---------------------------
# 1. 기본 유틸
# ---------------------------

def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(data, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ---------------------------
# 2. 룰 기반 필터
# ---------------------------

def rule_based_clean(text: str, name: str = "") -> str:
    if not text:
        return ""

    # 링크 제거
    text = re.sub(r'https?://\S+', '', text)

    # 이메일 제거
    text = re.sub(r'[\w\.-]+@[\w\.-]+\.\w+', '', text)

    # 전화번호 제거
    text = re.sub(r'01[0-9]-?\d{3,4}-?\d{4}', '', text)

    # 인사말 제거
    text = re.sub(r'^\s*안녕하세요[^\n]*\n?', '', text)
    text = re.sub(r'^\s*안녕하십니까[^\n]*\n?', '', text)

    # 끝 인사 제거
    text = re.sub(r'(감사합니다\.?|잘 부탁드립니다\.?)$', '', text)

    # 이름 제거
    if name:
        text = re.sub(rf'\n?\s*{re.escape(name)}\s*$', '', text)

    return text.strip()


# ---------------------------
# 3. LLM 검증
# ---------------------------

async def llm_validate_cover_letter(draft_text: str, context: dict) -> dict:
    prompt = f"""
다음 자기소개서를 검증하고 수정하세요.

[검증 기준]
1. 사용자 경험에 없는 내용이 있는가?
2. 성과 수치가 근거 없이 추가되었는가?
3. 채용공고와 무관한 내용이 있는가?
4. 과장된 표현이 있는가?
5. 자소서 문체가 자연스러운가?

[수정 규칙]
- 잘못된 내용은 제거 또는 수정
- 없는 정보는 추가하지 말 것
- 자연스럽게 다시 작성
- 반드시 JSON으로 출력

[출력 스키마]
{{
  "issues": [],
  "corrected_text": ""
}}

[사용자 정보]
{json.dumps(context["user_profile"], ensure_ascii=False)}

[자소서]
{draft_text}
"""

    response = await client.chat.completions.create(
        model="gpt-5-mini",
        messages=[
            {"role": "system", "content": "너는 자기소개서를 검증하는 전문가다."},
            {"role": "user", "content": prompt}
        ],
        response_format={"type": "json_object"}
    )

    return json.loads(response.choices[0].message.content)


# ---------------------------
# 4. 최종 마무리
# ---------------------------

def ensure_strong_ending(text: str) -> str:
    if not text.endswith(("기여하겠습니다.", "성장하겠습니다.")):
        text += "\n\n데이터 기반 문제 해결 역량을 바탕으로 서비스 개선에 실질적으로 기여하겠습니다."
    return text


# ---------------------------
# 5. 메인 실행
# ---------------------------

async def main():
    draft_data = load_json("./data/cover_letter_draft.json")

    context = draft_data["context"]
    name = context["user_profile"].get("name", "")

    validated_cover_letters = []

    for item in draft_data["cover_letters"]:
        version = item.get("version", "")
        strategy = item.get("strategy", "")
        draft = item.get("draft", {})

        raw_text = draft.get("full_cover_letter", "")

        # 1. 룰 기반 정리
        cleaned = rule_based_clean(raw_text, name)

        # 2. LLM 검증
        validated = await llm_validate_cover_letter(cleaned, context)
        corrected_text = validated.get("corrected_text", cleaned)

        # 3. 마지막 보정
        final_text = ensure_strong_ending(corrected_text)

        validated_cover_letters.append({
            "version": version,
            "strategy": strategy,
            "original": raw_text,
            "cleaned": cleaned,
            "issues": validated.get("issues", []),
            "final": final_text
        })

    result = {
        "selected_job": draft_data.get("selected_job", {}),
        "job_source": draft_data.get("job_source", {}),
        "context": context,
        "validated_cover_letters": validated_cover_letters
    }
    cover_letters = draft_data.get("cover_letters", [])
    if not cover_letters:
        print("검증할 자소서 버전이 없습니다.")
        return

    save_json(result, "./data/cover_letter_final.json")

    print("\n최종 자소서들:\n")
    for item in validated_cover_letters:
        print("=" * 100)
        print(f"[{item['version']}] strategy={item['strategy']}")
        print(item["final"])
        print("=" * 100)


if __name__ == "__main__":
    asyncio.run(main())