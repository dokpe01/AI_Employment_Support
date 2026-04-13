import sys
import os
import json
import time
import shutil
import asyncio
from datetime import datetime
from dotenv import load_dotenv
from sqlalchemy import text
from data_crawling import run_parallel_scraping
from duplicate import process_deduplication
from data_ocr import run_detail_process
import LLM as LLM
from async_database import AsyncSessionLocal
from async_models import Enter

current_dir = os.path.dirname(os.path.abspath(__file__))

if sys.platform.startswith("win"):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

load_dotenv()


async def get_user_keywords(user_id):
    async with AsyncSessionLocal() as session:
        try:
            result = await session.execute(
                text('SELECT job FROM "User" WHERE id = :id'),
                {"id": user_id}
            )
            row = result.first()
            if row and row[0]:
                return [k.strip() for k in row[0].split(',')]
        except Exception as e:
            print(f"DB 키워드 조회 중 에러: {e}")
        return None


def load_json_file(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)


def to_text(value):
    if value is None:
        return None
    if isinstance(value, list):
        return "\n".join(str(v) for v in value)
    return str(value)


def build_content_map(ocr_data):
    """OCR 결과 파일에서 url별 content 매핑 생성"""
    content_map = {}

    for item in ocr_data:
        url = to_text(item.get("url"))
        content = to_text(item.get("content"))

        if url and content:
            content_map[url] = content

    return content_map


def copy_file_if_exists(src, dst):
    """파일이 존재하면 복사"""
    if os.path.exists(src):
        shutil.copy2(src, dst)
        print(f"파일 복사 완료: {src} -> {dst}")
    else:
        print(f"복사할 파일이 없음: {src}")


async def get_existing_urls():
    async with AsyncSessionLocal() as session:
        result = await session.execute(text('SELECT url FROM "Enter"'))
        return {row[0] for row in result.fetchall() if row[0]}


async def prepare_final_data(data_list, content_map):
    existing_urls = await get_existing_urls()
    seen = set()
    prepared = []

    for item in data_list:
        url = to_text(item.get("url"))
        if not url:
            continue
        if url in existing_urls:
            continue
        if url in seen:
            continue

        seen.add(url)

        prepared.append({
            "name": to_text(item.get("name")) or "정보없음",
            "period": to_text(item.get("period")) or "미정",
            "job": to_text(item.get("job")) or "",
            "location": to_text(item.get("location")) or "",
            "work": to_text(item.get("work")),
            "qual": to_text(item.get("qual")),
            "prefer": to_text(item.get("prefer")),
            "procedure": to_text(item.get("procedure")),
            "docs": to_text(item.get("docs")),
            "apply": to_text(item.get("apply")) or "미기재",
            "url": url,
            "source": to_text(item.get("source")) or "unknown",
            "career": to_text(item.get("career")),
            "collected_at": to_text(item.get("collected_at")),
            "content": content_map.get(url, "")
        })

    return prepared


async def insert_enter_data(data_list):
    if not data_list:
        print("DB에 저장할 데이터가 없습니다.")
        return

    async with AsyncSessionLocal() as session:
        try:
            for item in data_list:
                new_data = Enter(**item)
                session.add(new_data)

            await session.commit()
            print(f"{len(data_list)}개 데이터 DB 저장 완료")

        except Exception as e:
            await session.rollback()
            print(f"DB 저장 중 에러: {e}")


async def run_total_automation(user_id):
    start_total = time.time()

    keywords = await get_user_keywords(user_id)
    if not keywords:
        print(f"사용자(ID: {user_id})의 희망직종이 설정되지 않았습니다.")
        return

    raw_list = run_parallel_scraping(keywords, max_items_per_site=20)
    if not raw_list:
        print("크롤링 결과가 없습니다.")
        return

    existing_urls = await get_existing_urls()
    new_raw_list = [
        item for item in raw_list
        if item.get("url") and item.get("url") not in existing_urls
    ]

    if not new_raw_list:
        print("새로운 공고가 없습니다. 작업을 종료합니다.")
        return

    data_dir = os.path.join(current_dir, "data")
    os.makedirs(data_dir, exist_ok=True)

    run_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_output_dir = os.path.join(current_dir, "run_outputs", run_timestamp)
    os.makedirs(run_output_dir, exist_ok=True)

    raw_path = os.path.join(data_dir, "total_site_link_final.json")
    refined_path = os.path.join(data_dir, "refined_data.json")
    ocr_output_path = os.path.join(data_dir, "ocr_data.json")
    final_output_path = os.path.join(data_dir, "LLM_data.json")

    with open(raw_path, "w", encoding="utf-8") as f:
        json.dump(new_raw_list, f, ensure_ascii=False, indent=4)

    process_deduplication(raw_path, refined_path)
    run_detail_process(refined_path, ocr_output_path, workers=3)

    await LLM.main()

    print("OCR 파일 존재 여부:", os.path.exists(ocr_output_path))
    print("LLM 파일 존재 여부:", os.path.exists(final_output_path))

    if not os.path.exists(ocr_output_path):
        print("OCR 결과 파일이 없습니다.")
        return

    if not os.path.exists(final_output_path):
        print("LLM 결과 파일이 없습니다.")
        return

    ocr_data = load_json_file(ocr_output_path)
    final_data = load_json_file(final_output_path)
    content_map = build_content_map(ocr_data)
    prepared_data = await prepare_final_data(final_data, content_map)
    print("최종 저장 대상 개수:", len(prepared_data))

    await insert_enter_data(prepared_data)

    copy_file_if_exists(raw_path, os.path.join(run_output_dir, "total_site_link_final.json"))
    copy_file_if_exists(refined_path, os.path.join(run_output_dir, "refined_data.json"))
    copy_file_if_exists(ocr_output_path, os.path.join(run_output_dir, "ocr_data.json"))
    copy_file_if_exists(final_output_path, os.path.join(run_output_dir, "LLM_data.json"))

    summary = {
        "run_timestamp": run_timestamp,
        "raw_count": len(raw_list),
        "new_raw_count": len(new_raw_list),
        "ocr_count": len(ocr_data),
        "final_count": len(final_data),
        "prepared_count": len(prepared_data),
        "saved_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }

    summary_path = os.path.join(run_output_dir, "run_summary.json")
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=4)

    print(f"실행 결과 저장 폴더: {run_output_dir}")

    end_total = time.time()
    print(f"\n모든 자동화 공정 완료! (총 소요 시간: {round(end_total - start_total, 2)}초)")


if __name__ == "__main__":
    print(f"자동화 작업을 시작합니다: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    try:
        asyncio.run(run_total_automation("qwer"))
    except Exception as e:
        print(f"에러 발생: {e}")
        exit(1)