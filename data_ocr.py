import json
import time
import requests
import cv2
import numpy as np
import pytesseract
import re
from PIL import Image
from io import BytesIO
from concurrent.futures import ThreadPoolExecutor
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager

# 텐서렉트(OCR) (경로 확인 필수)
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

def perform_ocr(image_url):
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        res = requests.get(image_url, headers=headers, timeout=5)
        img = Image.open(BytesIO(res.content))
        #색상 공간에서 그레이스케일로 변환, 이진화
        cv_img = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2GRAY)
        cv_img = cv2.threshold(cv_img, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]
        return pytesseract.image_to_string(cv_img, lang='kor+eng', config='--psm 3').strip()
    except:
        return ""

def get_fast_driver():
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36")
    
    # 불필요한 알림 차단
    prefs = {"profile.default_content_setting_values.notifications": 2}
    options.add_experimental_option("prefs", prefs)
    
    return webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

def process_single_job(job):
    driver = get_fast_driver()

    try:
        driver.get(job['url'])
        time.sleep(3) 
        full_content = ""
        collected_imgs = set()
        ocr_results = []

        # 1. 원티드 사이트
        if job['source'] == 'wanted':
            try:
                more_btn = driver.find_elements(By.XPATH, "//span[contains(text(), '상세 정보 더 보기')]")
                if more_btn: driver.execute_script("arguments[0].click();", more_btn[0])
                time.sleep(1)
                full_content = driver.find_element(By.CSS_SELECTOR, "article[class*='JobDescription']").text
                # [원티드 전용 주소 추출]
                location_el = driver.find_elements(By.CSS_SELECTOR, "div[class*='JobWorkPlace'] span.wds-1td1qmv")
                if location_el:
                    job['location'] = location_el[0].text.strip()
                
            except: pass

        # 2. 잡플래닛 사이트
        elif job['source'] == 'jobplanet':
            try:
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(2)

                detail_content = driver.find_elements(By.CSS_SELECTOR, "section.recruitment-detail .recruitment-detail__box")
                parts = []
                for content_el in detail_content:
                    class_attr = content_el.get_attribute("class")
                    if 'recruitment-summary' in class_attr:
                        continue
                    if 'js-image' in class_attr:
                        continue
                    iframes = content_el.find_elements(By.TAG_NAME, "iframe")
                    if iframes:
                        try:
                            driver.switch_to.frame(iframes[0])
                            inner_text = driver.find_element(By.TAG_NAME, "body").text.strip()
                            if inner_text:
                                parts.append(f"[상세 내용]\n{inner_text}")

                            inner_imgs = driver.find_elements(By.TAG_NAME, "img")
                            for img in inner_imgs:
                                src = img.get_attribute('src')
                                if src and 'http' in src and 'logo' not in src.lower():
                                    res = perform_ocr(src)
                                    if len(res) > 30: parts.append(f"[이미지 OCR]\n{res}")
                            
                            driver.switch_to.default_content() 
                        except:
                            driver.switch_to.default_content()
                            
                    else:
                        text = content_el.text.strip()
                        if text:
                            parts.append(text)

                full_content = "\n\n".join(parts)
            except Exception as e:
                print(f"⚠️ 잡플래닛 정밀 추출 에러: {e}")

        # 3. 사람인 사이트
        elif job['source'] == 'saramin':
            try:
                content_el = driver.find_elements(By.CSS_SELECTOR, ".user_content, .job_detail, .vac_re_content")
                if content_el:
                    full_content = content_el[0].text.strip()
                if not full_content:
                    iframes = driver.find_elements(By.CSS_SELECTOR, "iframe[id*='iframe']")
                    if iframes:
                        driver.switch_to.frame(iframes[0])
                        full_content = driver.find_element(By.TAG_NAME, "body").text.strip()
                        driver.switch_to.default_content()
            except: pass

        # 4. 잡코리아 사이트 
        elif job['source'] == 'jobkorea':
            try:
                outer_parts = []
                selectors = ["[data-sentry-component='RecruitmentGuidelines']", "[data-sentry-component='Qualification']", "#application-section"]
                for sel in selectors:
                    els = driver.find_elements(By.CSS_SELECTOR, sel)
                    if els: outer_parts.append(els[0].text.strip())
                inner_content = ""
                iframes = driver.find_elements(By.CSS_SELECTOR, "#details-section iframe, #gib_frame")
                if iframes:
                    driver.switch_to.frame(iframes[0])
                    inner_content = driver.find_element(By.TAG_NAME, "body").text.strip()
                    inner_imgs = driver.find_elements(By.TAG_NAME, "img")
                    for img in inner_imgs:
                        src = img.get_attribute('src')
                        if src and 'http' in src and 'logo' not in src.lower() and src not in collected_imgs:
                            collected_imgs.add(src)
                            res = perform_ocr(src)
                            if len(res) > 30: ocr_results.append(res)
                    driver.switch_to.default_content()
                
                full_content = "\n\n".join(outer_parts) + f"\n\n[상세본문]\n{inner_content}"
            except: pass

        # 하이브리드 OCR 추가 실행
        all_imgs = driver.find_elements(By.TAG_NAME, "img")
        for img in all_imgs:
            src = img.get_attribute('src')
            if src and 'http' in src and 'logo' not in src.lower() and src not in collected_imgs:
                collected_imgs.add(src)
                res = perform_ocr(src)
                if len(res) > 40: ocr_results.append(res)
        
        if ocr_results:
            full_content += "\n\n[이미지 내 추출 정보]\n" + "\n".join(ocr_results)
        
        job['content'] = full_content.strip()

        return job

    except Exception as e:
        print(f"❌ 에러 발생 ({job['url']}): {e}")
        return job
    finally:
        driver.quit()

if __name__ == "__main__":
    with open("./data/refined_data.json", "r", encoding="utf-8") as f:
        job_list = json.load(f)

    print(f"🚀 {len(job_list)}건에 대해 하이브리드 정밀 수집을 시작합니다.")
    start_time = time.time()

    # 2. 병렬 실행 (컴퓨터 사양에 따라 max_workers 조절)
    with ThreadPoolExecutor(max_workers=3) as executor:
        final_results = list(executor.map(process_single_job, job_list))

    # 3. 결과 저장
    with open("./data/ocr_data.json", "w", encoding="utf-8") as f:
        json.dump(final_results, f, ensure_ascii=False, indent=4)

    print(f"\n✨ 전 과정 완료! 소요 시간: {round(time.time() - start_time, 2)}초")