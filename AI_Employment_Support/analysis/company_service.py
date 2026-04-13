# analysis/company_service.py

import os
import time
import requests
from dotenv import load_dotenv
from newspaper import Article
from openai import AsyncOpenAI

load_dotenv()

NAVER_CLIENT_ID = os.getenv("NAVER_CLIENT_ID")
NAVER_CLIENT_SECRET = os.getenv("NAVER_CLIENT_SECRET")

client = AsyncOpenAI(api_key=os.getenv("OPENAI"))


def get_company_news_data(company_name, count=3):
    url = "https://openapi.naver.com/v1/search/news.json"
    headers = {
        "X-Naver-Client-Id": NAVER_CLIENT_ID,
        "X-Naver-Client-Secret": NAVER_CLIENT_SECRET
    }
    params = {
        "query": company_name,
        "display": count,
        "sort": "sim"
    }

    news_items = []

    try:
        response = requests.get(url, headers=headers, params=params, timeout=10)
        items = response.json().get("items", [])

        for item in items:
            link = item.get("originallink") or item.get("link")
            if not link:
                continue

            try:
                article = Article(link, language='ko')
                article.download()
                article.parse()

                if len(article.text.strip()) > 100:
                    news_items.append({
                        "title": article.title,
                        "content": article.text[:800],
                        "link": link
                    })
            except:
                continue

            time.sleep(0.3)

    except Exception as e:
        print(f"[뉴스 수집 오류] {company_name}: {e}")

    return news_items

async def generate_company_analysis(company_name, job_description, news_list):
    news_context = "\n".join(
        [f"뉴스: {n['title']}\n내용: {n['content']}" for n in news_list]
    ) if news_list else "최근 뉴스 없음"

    prompt = f"""
            당신은 전문 기업 분석가이자 헤드헌터입니다.

            아래 정보를 기반으로 기업 분석을 수행하세요.

            [채용공고]
            {job_description}

            [뉴스]
            {news_context}

            ---

            # 분석 요청 항목:
            1. 기업 개요: 이 기업이 어떤 회사인지 설명
            2. 비즈니스 모멘텀: 최근 뉴스 + 채용 직무를 연결하여 현재 기업 상황 분석
            3. 조직의 지향점과 미션: 기업이 추구하는 방향성과 목표
            4. 인재상 & 조직문화: 기업이 원하는 인재와 조직 분위기
            5. 분석가적 제언: 데이터 분석가 기준 지원 전략 및 면접 준비

            ---

            반드시 아래 JSON 형식으로만 응답하세요:

            {{
            "summary": "전체를 한 줄로 요약",
            "company_overview": "1번 내용",
            "momentum": "2번 내용",
            "mission": "3번 내용",
            "culture": "4번 내용",
            "strategy": "5번 내용"
            }}
            """

    try:
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7
        )

        return response.choices[0].message.content

    except Exception as e:
        print(f"[LLM 오류] {company_name}: {e}")
        return "분석 실패"