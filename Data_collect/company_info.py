import pandas as pd
import json
import time
import os
import requests
from dotenv import load_dotenv
from newspaper import Article
from openai import OpenAI
from datetime import datetime

# 1. 환경 설정 및 초기화
load_dotenv()
NAVER_CLIENT_ID = os.getenv("NAVER_CLIENT_ID")
NAVER_CLIENT_SECRET = os.getenv("NAVER_CLIENT_SECRET")
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# [기능 1] 네이버 뉴스 검색 및 본문 추출 (리스트 형태로 반환)
def get_company_news_data(company_name, count=3):
    url = f"https://openapi.naver.com/v1/search/news.json?query={company_name}&display={count}&sort=sim"
    headers = {
        "X-Naver-Client-Id": NAVER_CLIENT_ID,
        "X-Naver-Client-Secret": NAVER_CLIENT_SECRET
    }

    news_items = []
    try:
        response = requests.get(url, headers=headers)
        items = response.json().get('items', [])
        
        for item in items:
            link = item.get('originallink') or item.get('link')
            try:
                article = Article(link, language='ko')
                article.download()
                article.parse()
                if len(article.text) > 100:
                    news_items.append({
                        "title": article.title,
                        "content": article.text[:800] # 분석 및 확인용 800자
                    })
            except:
                continue
            time.sleep(0.5)
    except Exception as e:
        print(f"뉴스 검색 중 오류: {e}")
    
    return news_items

# [기능 2] 메인 실행 파이프라인
def run_full_report():
    try:
        with open('./data/LLM_data.json', 'r', encoding='utf-8') as f:
            df_llm = pd.DataFrame(json.load(f))
        with open('./data/ocr_data.json', 'r', encoding='utf-8') as f:
            df_ocr = pd.DataFrame(json.load(f))
        
        df = pd.merge(df_llm, df_ocr[['company', 'content']], 
                      left_on='name', right_on='company', how='left')
    except Exception as e:
        print(f"데이터 로드 실패: {e}")
        return
    
    final_results = []
    for _, row in df.head(2).iterrows():
        company_name = row['name']
        print(f"\n" + "-"*100)
        print(f"기업명: {company_name}")
        print("-"*100)
        # 1. 뉴스 데이터 수집 및 출력
        news_list = get_company_news_data(company_name)
        news_context_for_llm = "\n".join([f"뉴스: {n['title']}\n내용: {n['content']}" for n in news_list])

        # 2. LLM 분석 수행
        job_description = str(row['content']) if pd.notna(row['content']) else "상세 공고 없음"
        
        prompt = f"""
        당신은 전문 기업분석가이자 헤드헌터입니다. 제공된 자료를 바탕으로 '{company_name}'에 대한 입체적 분석 리포트를 작성하세요.

        [자료 1: 채용공고 상세내용]
        {job_description}

        [자료 2: 최신 뉴스 소식]
        {news_context_for_llm if news_list else "최근 뉴스 없음"}

        ---
        #분석 요청 항목:
        1. 기업인지에 대한 설명
        2. 비즈니스 모멘텀: 최근 뉴스와 채용 직무를 연결했을 때, 이 회사는 현재 어떤 변화(확장, 위기, 전환 등)의 중심에 있습니까?
        3. 조직의 지향점과 미션: 이 기업이 시장에서 도달하고자 하는 궁극적인 목표와 가치는 무엇인가?
        4. 인재상 & 조직 문화: 공고의 말투와 뉴스에 나타난 대외 이미지를 종합할 때, 이 기업이 생각하는 인재상의 기준은 무엇인가? 그 인재상을 위해 필요한 점이 무엇인지 같이 분석해줘
        5. 분석가적 제언: 만약 데이터 분석가로서 이 회사에 지원한다면, 지원동기, 직무 역량, 면접 답변 준비를 어떻게 하면 좋을까요?
        """

        analysis_report = "분석 실패"
        try:
            print(f"[{company_name}] LLM 전략 리포트 생성 중...")
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7
            )
            analysis_report = response.choices[0].message.content
        except Exception as e:
            print(f" LLM 분석 오류: {e}")

        # 3. 데이터 통합 및 결과 저장
        result_entry = {
            "company_name": company_name,
            "analysis_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "source_data": {
                "job_description": job_description,
                "news_data": news_list
            },
            "analysis_report": analysis_report
        }
        final_results.append(result_entry)
        
        # 화면 출력 (진행 확인용)
        print(f"[{company_name}] 분석 완료")
        time.sleep(2)

    # 4. JSON 파일 저장
    output_path = './data/final_company_analysis.json'
    # 폴더가 없을 경우 생성
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(final_results, f, ensure_ascii=False, indent=4)
    
    print(f"\n모든 결과가 '{output_path}'에 저장되었습니다.")

if __name__ == "__main__":
    run_full_report()