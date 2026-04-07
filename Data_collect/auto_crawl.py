import json
import time
import asyncio

from Data_collect.data_crawling import run_parallel_scraping
from Data_collect.duplicate import process_deduplication
from Data_collect.data_ocr import run_detail_process  
import Data_collect.LLM as LLM 

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
import os
from dotenv import load_dotenv

load_dotenv()
db_url = os.getenv("DATABASE_URL")
engine = create_async_engine(db_url)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
async def get_user_keywords(user_id):
    """DB에서 특정 사용자의 희망 직종을 가져옴"""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            text('SELECT job FROM "User" WHERE id = :id'),
            {"id":user_id}
        )
        row = result.fetchone()
        if row and row[0]:
            # 쉼표로 구분된 문자열을 리스트로 변환
            return [k.strip() for k in row[0].split(',')]
        return None
    
async def run_total_automation(job):
    start_total = time.time()
    # 추후 사용자가 선택한 직무가 들어가도록 수정 예정
    keywords = await get_user_keywords(job)
    if not keywords:
        print(f"사용자(ID: {id})의 희망직종이 설정되지 않았습니다.")

    # 각 사이트에서 링크 크롤링 
    # raw_list = run_parallel_scraping(keywords, max_items_per_site=20)
    # raw_path = "./data/total_site_link_final.json"
    # with open(raw_path, "w", encoding="utf-8") as f:
    #     json.dump(raw_list, f, ensure_ascii=False, indent=4)
    # refined_path = "./data/refined_data.json"

    # # 중복 공고 제거
    # process_deduplication(raw_path, refined_path)

    # #OCR
    # ocr_output_path = "./data/ocr_data.json"
    # run_detail_process(refined_path, ocr_output_path, workers=3)
    
    #LLM 가공 (비동기)
    await LLM.main()
    end_total = time.time()
    print(f"\n✨ 모든 자동화 공정 완료! (총 소요 시간: {round(end_total - start_total, 2)}초)")

if __name__ == "__main__":
    import asyncio
    asyncio.run(run_total_automation("skdud1"))