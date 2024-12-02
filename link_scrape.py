import boto3
from botocore.exceptions import NoCredentialsError, ClientError
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager
import time
from datetime import datetime

# AWS S3 클라이언트 설정
s3_client = boto3.client('s3')

# Selenium 웹 드라이버 설정
driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()))

# 시작 URL (첫 페이지 URL)
search_keyword = "데이터 엔지니어"  # 검색 키워드
base_url = f"https://www.jobkorea.co.kr/Search/?stext={search_keyword}&tabType=recruit&Page_No="

# 오늘 날짜로 txt 파일 이름 설정
today_date = datetime.now().strftime("%Y%m%d")
file_name = f"{today_date}.txt"

# 이미 저장된 링크 불러오기 (S3에서만)
def load_existing_links(bucket_name, s3_file_path):
    existing_links = set()

    # S3 파일에서 링크 읽기
    try:
        s3_client.download_file(bucket_name, s3_file_path, file_name)
        print(f"S3 파일을 로컬로 다운로드: {file_name}")
        with open(file_name, "r", encoding="utf-8") as file:
            existing_links.update(line.strip() for line in file.readlines())
    except ClientError as e:
        if e.response['Error']['Code'] == "404":
            print("S3에 기존 파일이 존재하지 않습니다. 새로 생성합니다.")
        else:
            print(f"S3 파일 다운로드 중 오류 발생: {e}")

    return existing_links

# S3에 파일 업로드 함수
def upload_to_s3(local_file_path, bucket_name, s3_file_path):
    try:
        s3_client.upload_file(local_file_path, bucket_name, s3_file_path)
        print(f"파일이 S3에 성공적으로 업로드되었습니다. S3 경로: s3://{bucket_name}/{s3_file_path}")
    except NoCredentialsError:
        print("AWS 자격 증명 오류: 자격 증명이 없습니다.")
    except Exception as e:
        print(f"S3 업로드 중 오류 발생: {e}")

# 페이지 크롤링 함수
def scrape_links():
    bucket_name = "t2jt"
    s3_file_path = f"job/DE/sources/jobkorea/links/{file_name}"
    
    # 기존 링크 로드 (S3에서만)
    existing_links = load_existing_links(bucket_name, s3_file_path)

    new_links = []  # 새로 크롤링한 URL 저장
    page_number = 1  # 첫 페이지 번호
    print(f"검색 키워드: {search_keyword}")  # 검색 키워드 출력

    while True:
        # 페이지 열기
        url = f"{base_url}{page_number}"
        driver.get(url)
        time.sleep(3)  # 페이지 로딩 대기

        # 검색 결과가 없으면 종료
        try:
            no_results_message = driver.find_element(By.CLASS_NAME, "list-empty-result")
            if "검색결과가 없습니다" in no_results_message.text:
                print(f"{page_number}에 수집할 링크가 없으므로 링크 수집을 멈춥니다.")
                break
        except Exception:
            print(f"페이지 {page_number}: 검색 결과가 있습니다. 계속 진행합니다...")

        # article class="list" 내부의 링크 가져오기
        page_links = []  # 해당 페이지에서 새로 수집한 링크 저장
        try:
            article_list = driver.find_element(By.CLASS_NAME, "list")  # article class="list" 선택
            links = article_list.find_elements(By.TAG_NAME, "a")  # 해당 article 내부의 <a> 태그 찾기

            for link in links:
                href = link.get_attribute("href")
                if href and href.startswith("https://www.jobkorea.co.kr/Recruit/GI_Read"):
                    # 'PageGbn=HH'가 포함된 링크는 제외
                    if "?PageGbn=HH" not in href:
                        # URL에서 "?"로 나눠서 앞부분만 가져오기
                        clean_href = href.split('?')[0]
                        if clean_href not in existing_links:
                            page_links.append(clean_href)  # 새 링크를 리스트에 추가
                            existing_links.add(clean_href)  # 중복 방지
        except Exception as e:
            print(f"페이지 {page_number}에서 링크를 가져오는 데 오류가 발생했습니다: {e}")

        # 해당 페이지의 데이터를 저장
        if page_links:
            new_links.extend(page_links)

        # 페이지 번호 증가
        page_number += 1

    # 크롤링한 데이터 출력
    print(f"{len(new_links)}개의 새로운 링크를 발견하였습니다.")

    # S3에 새 데이터 저장
    if new_links:
        with open(file_name, "w", encoding="utf-8") as file:
            for link in new_links:
                file.write(f"{link}\n")

        upload_to_s3(file_name, bucket_name, s3_file_path)
        print(f"총 {len(new_links)}개의 링크를 S3에 저장하였습니다.")
    else:
        print("새로 저장할 링크가 없습니다.")

# 크롤링 실행
scrape_links()

# 브라우저 종료
driver.quit()
