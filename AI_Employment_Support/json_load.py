import json
import os
from database import SessionLocal
import models

JSON_FILE_PATH = os.path.join("data", "data.json")
CONTENT_FILE_PATH = os.path.join("data", "ocr_data.json")


def safe_text(v):
    if v is None:
        return None
    if isinstance(v, list):
        return "\n".join(str(x) for x in v)
    if isinstance(v, dict):
        return json.dumps(v, ensure_ascii=False)
    return str(v)


def normalize_url(url):
    if not url:
        return None

    url = str(url).strip()

    if "GI_Read/" in url:
        return url.split("GI_Read/")[1].split("?")[0]

    if "wanted.co.kr/wd/" in url:
        return url.split("/wd/")[1].split("?")[0]

    return url


def json_insert_to_enter():
    if not os.path.exists(JSON_FILE_PATH):
        print(f"파일을 찾을 수 없습니다: {JSON_FILE_PATH}")
        return

    if not os.path.exists(CONTENT_FILE_PATH):
        print(f"파일을 찾을 수 없습니다: {CONTENT_FILE_PATH}")
        return

    with open(JSON_FILE_PATH, "r", encoding="utf-8") as f:
        json_data = json.load(f)

    with open(CONTENT_FILE_PATH, "r", encoding="utf-8") as f:
        content_data = json.load(f)

    if isinstance(json_data, dict):
        json_data = [json_data]

    if isinstance(content_data, dict):
        content_data = [content_data]

    content_map = {}
    for item in content_data:
        norm_url = normalize_url(item.get("url"))
        if norm_url:
            content_map[norm_url] = safe_text(item.get("content"))

    print(f"data.json 개수: {len(json_data)}")
    print(f"ocr_data.json 개수: {len(content_data)}")
    print(f"url 기준 content 개수: {len(content_map)}")

    db = SessionLocal()
    try:
        insert_mappings = []
        matched_count = 0
        unmatched_count = 0

        for item in json_data:
            raw_url = item.get("url")
            norm_url = normalize_url(raw_url)
            matched_content = content_map.get(norm_url)

            if matched_content:
                matched_count += 1
            else:
                unmatched_count += 1
                print(f"[content 매칭 실패] name={item.get('name')}, url={raw_url}, norm={norm_url}")

            mapping = {
                "name": safe_text(item.get("name")),
                "period": safe_text(item.get("period")),
                "job": safe_text(item.get("job")),
                "location": safe_text(item.get("location")),
                "work": safe_text(item.get("work")),
                "qual": safe_text(item.get("qual")),
                "prefer": safe_text(item.get("prefer")),
                "procedure": safe_text(item.get("procedure")),
                "docs": safe_text(item.get("docs")),
                "apply": safe_text(item.get("apply")),
                "url": safe_text(raw_url),
                "source": safe_text(item.get("source", "Unknown")),
                "career": safe_text(item.get("career")),
                "collected_at": safe_text(item.get("collected_at")),
                "content": matched_content,
            }
            insert_mappings.append(mapping)

        print(f"content 매칭 성공: {matched_count}")
        print(f"content 매칭 실패: {unmatched_count}")

        db.bulk_insert_mappings(models.Enter, insert_mappings)
        db.commit()
        print(f"총 {len(insert_mappings)}개의 데이터를 'Enter' 테이블에 저장 완료!")

    except Exception as e:
        db.rollback()
        print(f"데이터 저장 중 에러 발생: {e}")
    finally:
        db.close()


if __name__ == "__main__":
    json_insert_to_enter()