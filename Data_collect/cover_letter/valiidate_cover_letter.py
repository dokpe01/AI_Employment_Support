import os
import re
import json
import asyncio
from openai import AsyncOpenAI
from dotenv import load_dotenv

load_dotenv()

client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(CURRENT_DIR)
DATA_DIR = os.path.join(BASE_DIR, "data")

def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(data, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def rule_based_clean(text: str, name: str = "") -> str:
    if not text:
        return ""

    text = re.sub(r'https?://\S+', '', text)
    text = re.sub(r'[\w\.-]+@[\w\.-]+\.\w+', '', text)
    text = re.sub(r'01[0-9]-?\d{3,4}-?\d{4}', '', text)

    text = re.sub(r'^\s*안녕하세요[^\n]*\n?', '', text)
    text = re.sub(r'^\s*안녕하십니까[^\n]*\n?', '', text)

    text = re.sub(r'(감사합니다\.?|잘 부탁드립니다\.?)$', '', text)

    if name:
        text = re.sub(rf'\n?\s*{re.escape(name)}\s*$', '', text)

    return text.strip()

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

def ensure_strong_ending(text: str) -> str:
    if not text:
        return ""

    good_endings = (
        "기여하겠습니다.",
        "성장하겠습니다.",
        "만들어가겠습니다.",
        "만들어내겠습니다.",
        "실현하겠습니다.",
        "돕겠습니다.",
        "보탬이 되겠습니다.",
    )

    if not text.endswith(good_endings):
        text += "\n\n데이터 기반 문제 해결 역량을 바탕으로 서비스 개선에 실질적으로 기여하겠습니다."

    return text

async def validate_cover_letters(draft_data: dict) -> dict:
    """
    서버에서 직접 호출하는 함수

    입력:
      draft_data (generate_cover_letters 결과)

    출력:
      최종 자소서 JSON
    """

    context = draft_data["context"]
    name = context["user_profile"].get("name", "")

    validated_cover_letters = []

    for item in draft_data["cover_letters"]:
        version = item.get("version", "")
        strategy = item.get("strategy", "")
        draft = item.get("draft", {})
        raw_text = draft.get("full_cover_letter", "")
        cleaned = rule_based_clean(raw_text, name)
        validated = await llm_validate_cover_letter(cleaned, context)
        corrected_text = validated.get("corrected_text", cleaned)
        final_text = ensure_strong_ending(corrected_text)

        validated_cover_letters.append({
            "version": version,
            "strategy": strategy,
            "original": raw_text,
            "cleaned": cleaned,
            "issues": validated.get("issues", []),
            "final": final_text
        })

    return {
        "selected_job": draft_data.get("selected_job", {}),
        "job_source": draft_data.get("job_source", {}),
        "context": context,
        "validated_cover_letters": validated_cover_letters
    }

async def main():
    draft_path = os.path.join(DATA_DIR, "cover_letter_draft.json")
    output_path = os.path.join(DATA_DIR, "cover_letter_final.json")

    try:
        draft_data = load_json(draft_path)
    except Exception as e:
        print(f"파일 로드 실패: {e}")
        return

    result = await validate_cover_letters(draft_data)

    save_json(result, output_path)

    print(f"\n최종 자소서 저장 완료: {output_path}")

    for item in result["validated_cover_letters"]:
        print("\n" + "=" * 100)
        print(f"[{item['version']}] strategy={item['strategy']}")
        print(item["final"])
        print("=" * 100)


if __name__ == "__main__":
    asyncio.run(main())