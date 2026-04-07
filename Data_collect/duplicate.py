

import json
import re
import time
from difflib import SequenceMatcher


def string_similarity(a, b):
    """두 문자열의 유사도를 0~1 사이로 반환"""
    return SequenceMatcher(None, a, b).ratio()


def clean_text(text):
    """비교를 위해 특수문자, 공백, (주) 등을 제거"""
    text = str(text)
    text = re.sub(r'\(주\)|㈜|\[.*?\]|\(.*?\)', '', text)
    text = re.sub(r'[^가-힣a-zA-Z0-9]', '', text)
    return text.strip()


def process_deduplication(input_file, output_file):
    start_time = time.time()
    with open(input_file, "r", encoding="utf-8") as f:
        jobs = json.load(f)
   
    unique_jobs = []
    duplicate_pairs = []

    for job in jobs:
        c_comp = clean_text(job.get('company', ''))
        c_tit = clean_text(job.get('title', ''))
       
        is_duplicate = False
       
        for u_job in unique_jobs:
            u_comp = clean_text(u_job['company'])
            u_tit = clean_text(u_job['title'])
           
            # 1. 회사명이 정제 후 동일한지 확인
            if c_comp == u_comp:
                # 2. 제목 유사도 측정
                sim = string_similarity(c_tit, u_tit)
               
                # 유사도 0.8(80%) 이상이면 중복으로 판정
                if sim >= 0.8:
                    is_duplicate = True
                    duplicate_pairs.append({
                        "original": f"[{u_job['source']}] {u_job['company']} | {u_job['title']}",
                        "duplicate": f"[{job['source']}] {job['company']} | {job['title']}",
                        "score": round(sim, 2)
                    })
                    break
       
        if not is_duplicate:
            unique_jobs.append(job)

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(unique_jobs, f, ensure_ascii=False, indent=4)
   
    end_time = time.time()
    print(f"\n 중복 제거 완료!")
    print(f"결과: {len(jobs)}건 -> {len(unique_jobs)}건 (총 {len(duplicate_pairs)}건 삭제)")
    print(f"소요 시간: {round(end_time - start_time, 2)}초")


if __name__ == "__main__":
    process_deduplication("./data/total_site_link_final.json", "./data/refined_data.json")


