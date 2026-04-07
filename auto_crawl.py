import json
import time
import asyncio

from data_crawling import run_parallel_scraping
from duplicate import process_deduplication
from data_ocr import run_detail_process  
import LLM 

def run_total_automation():
    start_total = time.time()
    # 추후 사용자가 선택한 직무가 들어가도록 수정 예정
    keywords = ["데이터 분석", "AI엔지니어"]

    # 각 사이트에서 링크 크롤링 
    raw_list = run_parallel_scraping(keywords, max_items_per_site=20)
    raw_path = "./data/total_site_link_final.json"
    with open(raw_path, "w", encoding="utf-8") as f:
        json.dump(raw_list, f, ensure_ascii=False, indent=4)
    refined_path = "./data/refined_data.json"

    # 중복 공고 제거
    process_deduplication(raw_path, refined_path)

    #OCR
    ocr_output_path = "./data/ocr_data.json"
    run_detail_process(refined_path, ocr_output_path, workers=3)
    
    #LLM 가공 (비동기)
    asyncio.run(LLM.main())
    end_total = time.time()
    print(f"\n✨ 모든 자동화 공정 완료! (총 소요 시간: {round(end_total - start_total, 2)}초)")

if __name__ == "__main__":
    run_total_automation()