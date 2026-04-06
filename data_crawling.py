import time
import json
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager
from concurrent.futures import ThreadPoolExecutor

# 채용공고 사이트[잡코리아, 사람인, 잡플래닛, 원티드]에서 공고 크롤링 
# 사용자의 희망직무를 검색하여 크롤링

# --- [공통 설정] ---
def get_driver(platform="common"):
    options = Options()
    options.add_argument("--headless")  #배포/고속 수집을 위해 창 숨김
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36")
   
    if platform == "wanted":
        # 원티드 전용: 권한 팝업 차단
        prefs = {"profile.default_content_setting_values.notifications": 2, "profile.default_content_setting_values.geolocation": 2}
        options.add_experimental_option("prefs", prefs)
   
    return webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

# 사이트1. 잡코리아 
def scrape_jobkorea(keyword, max_pages):
    driver = get_driver()
    seen_urls = set()
    target_links = []

    try:
        print(f"\n[잡코리아] '{keyword}' 수집 시작")
        for i in range(1, max_pages + 1):
            url = f"https://www.jobkorea.co.kr/Search?stext={keyword}&tabType=recruit&Page_No={i}"
            driver.get(url)
            time.sleep(4)
               
            company_spans = driver.find_elements(By.CSS_SELECTOR, "span.text-typo-b2-16.text-gray700")

            added_count = 0
            for span in company_spans:
                try:
                    company = span.text.strip().replace("㈜", "").replace("(주)", "").strip()
                    parent_a = span.find_element(By.XPATH, "./..") 
                    link = parent_a.get_attribute('href')
                    title_el = parent_a.find_element(By.XPATH, "../../..//span[contains(@class, 'font-semibold')]")
                    title = title_el.text.strip()

                    if link and link not in seen_urls:
                        target_links.append({
                            "keyword": keyword,
                            "title": title,
                            "company": company,
                            "url": link,
                            "source": "jobkorea"
                        })
                        seen_urls.add(link)
                        added_count += 1
                except:
                    continue

        return target_links

    finally:
        driver.quit()

# 사이트2. 사람인 
def scrape_saramin(keyword, max_pages):
    driver = get_driver()
    seen_urls = set()
    target_links = []

    try:
        print(f"\n [사람인] '{keyword}' 수집 시작")
        for i in range(1, max_pages + 1):
            url = f"https://www.saramin.co.kr/zf_user/search/recruit?searchword={keyword}&recruitPage={i}"
            driver.get(url)
            time.sleep(4)

            items = driver.find_elements(By.CSS_SELECTOR, "div.item_recruit")
            added_count = 0
            for item in items:
                try:
                    link_el = item.find_element(By.CSS_SELECTOR, "h2.job_tit a")
                    link = link_el.get_attribute('href')
                    if "saramin.co.kr" not in link:
                        link = "https://www.saramin.co.kr" + link
                    
                    title = link_el.get_attribute('title') or link_el.text.strip()
                    company_el = item.find_element(By.CSS_SELECTOR, "div.area_corp strong.corp_name a")
                    company = company_el.text.strip().replace("㈜", "").replace("(주)", "").strip()

                    if link and link not in seen_urls:
                        target_links.append({
                            "keyword": keyword,
                            "title": title,
                            "company": company,
                            "url": link,
                            "source": "saramin"
                        })
                        seen_urls.add(link)
                        added_count += 1
                except:
                    continue
            
            if added_count == 0: break
            
        return target_links
    finally:
        driver.quit()

# 사이트3. 잡플래닛
def scrape_jobplanet(keyword, max_items):
    driver = get_driver()
    seen_urls = set()
    target_links = []
    try:
        url = f"https://www.jobplanet.co.kr/search/job?&query={keyword}"
        driver.get(url)
        time.sleep(5)
        print(f"\n[잡플래닛] '{keyword}' 수집 시작")\
        # [단계 1] 목표 개수를 채울 때까지 스크롤 반복
        while len(target_links) < max_items:
            # 1. 현재 화면에 노출된 공고 링크들 찾기
            job_elements = driver.find_elements(By.CSS_SELECTOR, "a.group.z-0.block[title='페이지 이동']")
           
            for a_tag in job_elements:
                link = a_tag.get_attribute('href')
                if link and link not in seen_urls:
                    try:
                        title = a_tag.find_element(By.TAG_NAME, "h4").text.strip()
                        company = a_tag.find_element(By.TAG_NAME, "em").text.strip()
                        seen_urls.add(link)  
                        target_links.append({"keyword":keyword, 
                                             "title": title, 
                                             "company": company, 
                                             "url": link, 
                                             "source": "jobplanet"})
                    except:
                        continue

                if len(target_links) >= max_items:
                    break
            # 2. 아직 부족하다면 스크롤 내리기
            print(f"   ㄴ 현재 {len(target_links)}건 확보 중... 스크롤을 내립니다.")
            last_height = driver.execute_script("return document.body.scrollHeight")
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(3) # 로딩 대기
           
            # 더 이상 내려갈 곳이 없으면(공고가 바닥나면) 중단
            if driver.execute_script("return document.body.scrollHeight") == last_height:
                print("더 이상 불러올 공고가 없습니다.")
                break

        print(f"[잡플래닛] 리스트 수집 완료.({len(target_links)}건)")
        return target_links
    finally:
        driver.quit()

#[사이트4.원티드]
def scrape_wanted(keyword, max_items):
    driver = get_driver()
    seen_urls = set()
    target_links = []

    try:
        # 검색 페이지 접속 (포지션 탭)
        url = f"https://www.wanted.co.kr/search?query={keyword}&tab=position"
        driver.get(url)
        time.sleep(5)

        print(f"\n[원티드] '{keyword}' 수집 시작")
        # --- [단계 1] 리스트 수집 (무한 스크롤) ---
        while len(target_links) < max_items:
            # role="listitem" 속성을 가진 카드 요소를 모두 찾음
            job_cards = driver.find_elements(By.CSS_SELECTOR, "div[role='listitem']")
           
            if not job_cards:
                print("검색 결과가 없거나 아직 로딩 중입니다.")
                break

            for card in job_cards:
                try:
                    a_tag = card.find_element(By.TAG_NAME, "a")
                    link = a_tag.get_attribute('href')
                   
                    if link and link not in seen_urls:
                        title = a_tag.get_attribute('data-position-name')
                        company = a_tag.get_attribute('data-company-name')
                        seen_urls.add(link)
                        target_links.append({
                            "keyword":keyword, 
                            "title": title, 
                            "company": company,
                            "url": link,
                            "source" : "wanted"})
                        
                        if len(target_links) >= max_items:
                            break
                except:
                    continue
           
            if len(target_links) >= max_items:
                break
            # 스크롤 내리기 (추가 공고 로딩)
            last_height = driver.execute_script("return document.body.scrollHeight")
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(3)
           
            # 더 이상 로딩될 데이터가 없으면 중단
            if driver.execute_script("return document.body.scrollHeight") == last_height:
                print("모든 공고가 화면에 로딩되었습니다.")
                break
       
        print(f"[원티드] 리스트 수집 완료.({len(target_links)}건)")
        return target_links
    finally:
        driver.quit()


#[병렬실행]
def run_parallel_scraping(keywords, max_items_per_site=50):
    final_list = []
    # 각 키워드별로 실행할 작업 리스트 생성
    tasks = []
    for kw in keywords:
        tasks.append((scrape_wanted, kw, max_items_per_site))
        tasks.append((scrape_jobplanet, kw, max_items_per_site))
        tasks.append((scrape_saramin, kw, 5))  # max_pages=5
        tasks.append((scrape_jobkorea, kw, 5)) # max_pages=5


    print(f"🚀 병렬 엔진 가동: 총 {len(tasks)}개의 수집 작업을 동시 실행합니다.")
   
    # max_workers는 컴퓨터 사양에 맞게 조절 (4~8 추천)
    with ThreadPoolExecutor(max_workers=2) as executor:
        # 함수와 인자를 매핑하여 실행
        futures = [executor.submit(func, kw, val) for func, kw, val in tasks]
        for future in futures:
            try:
                result = future.result()
                if result:
                    final_list.extend(result)
            except Exception as e:
                print(f"⚠️ 작업 중 에러 발생: {e}")
               
    return final_list

# 실행
if __name__ == "__main__":
    test_keywords = ["데이터 분석", "AI엔지니어"]
    # 추후 사용자 희망직무로 들어올 수 있도록 할것!
    start_time = time.time()
   
    total_data = run_parallel_scraping(test_keywords)
   
    # 결과 저장
    output_filename = "total_site_link.json"
    with open(output_filename, "w", encoding="utf-8") as f:
        json.dump(total_data, f, ensure_ascii=False, indent=4)
       
    print(f"\n 수집 완료! 소요 시간: {round(time.time() - start_time, 2)}초")
    print(f"파일 저장됨: {output_filename} (총 {len(total_data)}건)")

