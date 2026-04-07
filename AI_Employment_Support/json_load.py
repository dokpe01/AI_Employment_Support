import json
import os
from sqlalchemy.orm import Session
from database import SessionLocal
import models

JSON_FILE_PATH = os.path.join("data", "LLM_data.json")

def json_insert_to_enter():
    if not os.path.exists(JSON_FILE_PATH):
        print(f"파일을 찾을 수 없습니다: {JSON_FILE_PATH}")
        return

    with open(JSON_FILE_PATH, 'r', encoding='utf-8') as f:
        json_data = json.load(f)

    if isinstance(json_data, dict):
        json_data = [json_data]

    db = SessionLocal()
    try:
        insert_mappings = []
        for item in json_data:
            def format_list(key):
                val = item.get(key, "")
                return "\n".join(val) if isinstance(val, list) else val

            mapping = {
                "name": item.get("name"),
                "period": str(item.get("period", "")),
                "job": item.get("job"),
                "location": item.get("location"),
                "work": format_list("work"),
                "qual": format_list("qual"),
                "prefer": format_list("prefer"),
                "procedure": item.get("procedure"),
                "docs": item.get("docs"),
                "apply": bool(item.get("apply", False)),
                "url": item.get("url"),
                "source": item.get("source", "Unknown")
            }
            insert_mappings.append(mapping)

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