import os
import json
import time
from datetime import datetime, timedelta
import re
import requests
from uuid import uuid4
import pymysql  # pymysql import 추가
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from collections import defaultdict
import boto3  # boto3 import 추가
import logging
from botocore.exceptions import NoCredentialsError

# AWS S3 연결 설정
s3_client = boto3.client('s3')

# 로깅 설정
logging.basicConfig(
    filename="log.txt",
    level=logging.INFO,
    format="%(message)s"
)

# AWS MySQL 연결 설정
db = pymysql.connect(
    host='43.201.40.223',          # AWS 퍼블릭 IP
    user='user',                # MySQL 사용자
    password='1234',            # MySQL 비밀번호
    database='testdb',          # 데이터베이스 이름
    charset='utf8mb4'
)

# 커서 생성
cursor = db.cursor()

# 테이블에 데이터 삽입을 위한 SQL 쿼리
insert_query = """
    INSERT INTO jobkorea (create_time, update_time, removed_time, site, job_title, due_type, due_date, company, post_title, notice_type, org_url, s3_text_url, s3_images_url, responsibility, qualification, preferential)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
"""

# Selenium 웹 드라이버 설정
driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()))

# S3에서 파일 읽기 함수
def read_s3_file(bucket_name, file_key):
    try:
        obj = s3_client.get_object(Bucket=bucket_name, Key=file_key)
        file_content = obj['Body'].read().decode('utf-8')
        return set(line.strip() for line in file_content.splitlines())
    except Exception as e:
        logging.error(f"[ERROR] S3 파일 읽기 실패: {file_key}, 에러: {e}")
        return set()

# S3 버킷과 파일 경로 설정
bucket_name = 't2jt'
prefix = 'job/DE/sources/jobkorea/links'

# 오늘 날짜 계산
today_date = datetime.now().strftime("%Y%m%d")

# 오늘 날짜 파일 경로 설정
today_links_file = f"{prefix}/{today_date}.txt"

# 가장 최근 날짜 파일 경로 가져오기 (오늘 날짜 파일 제외)
def get_latest_file_exclude_today(bucket_name, prefix, today_date):
    response = s3_client.list_objects_v2(Bucket=bucket_name, Prefix=prefix)
    if 'Contents' not in response:
        logging.error("S3 버킷에 파일이 존재하지 않습니다.")
        return None
    files = [content['Key'] for content in response['Contents']]
    # 오늘 날짜 파일을 제외한 파일만 필터링
    files = [file for file in files if today_date not in file]
    if not files:
        logging.error("오늘 날짜 파일을 제외한 파일이 없습니다.")
        return None
    files.sort(reverse=True)  # 최신 파일을 맨 위로 정렬
    return files[0] if files else None

# 최신 날짜 파일 가져오기 (오늘 날짜 제외)
latest_file = get_latest_file_exclude_today(bucket_name, prefix, today_date)

if latest_file:
    # 최신 파일명에서 날짜 추출
    latest_date = latest_file.split('/')[-1].split('.')[0]  # 예: '20241202'
    latest_links_file = f"{prefix}/{latest_date}.txt"

    logging.info(f"가장 최신 파일 (오늘 제외): {latest_links_file}")
else:
    logging.error("최신 파일을 찾을 수 없습니다.")
    driver.quit()
    exit()

# 오늘 날짜 파일 읽기
today_urls = read_s3_file(bucket_name, today_links_file)

# 최신 날짜 파일 읽기
latest_urls = read_s3_file(bucket_name, latest_links_file)

# URL 비교
if today_urls and latest_urls:
    # 새 URL 계산
    new_today_urls = today_urls - latest_urls
    # 제거된 URL 계산
    removed_urls = latest_urls - today_urls

    logging.info(f"새 URL 수: {len(new_today_urls)}, 제거된 URL 수: {len(removed_urls)}")

else:
    logging.error(f"{today_links_file} 또는 {latest_links_file}을(를) 읽을 수 없습니다.")

# 출력: 어제는 있었지만 오늘은 없는 URL 수
print(f"[INFO] remove된 공고 수: {len(removed_urls)}개")

# 출력: 어제는 없었지만 오늘은 있는 URL 수
print(f"[INFO] 오늘 새로 create된 공고 수: {len(new_today_urls)}개")

# 작업 상태 기록 함수
def log_status(url, status, task_status):
    time_now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    logging.info(f"{url} - {status} - {task_status} - {time_now}")

# text와 image 디렉토리 생성 (현재 작업 디렉토리에서)
text_dir = "txt"
image_dir = "images"
if not os.path.exists(text_dir):
    os.makedirs(text_dir)
if not os.path.exists(image_dir):
    os.makedirs(image_dir)

processed_count = 0  # 처리된 파일 수 카운트
error_count = 0  # 에러 총 수 카운트
error_types = defaultdict(int)  # 에러 종류별 카운트
skipped_urls = []  # 크롤링하지 않은 URL 리스트

# 회사 이름을 추출하는 함수
def extract_company(text):
    match = re.search(r"(.*?)(를 소개해요)", text)
    if match:
        return match.group(1).strip()  # "를 소개해요" 앞의 텍스트
    return ""  # "를 소개해요"가 없으면 빈 문자열

# 이미지 다운로드 함수
def download_image(img_url, image_path):
    try:
        response = requests.get(img_url)
        if response.status_code == 200:
            with open(image_path, "wb") as file:
                file.write(response.content)
            return True
        else:
            print(f"[ERROR] {img_url}에서 이미지를 다운로드할 수 없습니다.")
            return False
    except Exception as e:
        print(f"[ERROR] {img_url}에서 이미지를 다운로드하는 중 오류가 발생했습니다.")
        print(e)
        return False

# S3에 파일 업로드 함수
def upload_to_s3(local_file_path, bucket_name, s3_path):
    try:
        s3_client.upload_file(local_file_path, bucket_name, s3_path)
        print(f"[INFO] {local_file_path}를 s3://{bucket_name}에 업로드했습니다.")
        return f"s3://{bucket_name}/{s3_path}"
    except NoCredentialsError:
        print("[ERROR] s3 자격 증명이 없습니다.")
        return None
    except Exception as e:
        print(f"[ERROR] {local_file_path}를 S3로 업로드하는 중 오류가 발생했습니다.")
        return None

# 각 링크 처리
for url in new_today_urls:
    url = url.strip()  # 링크에서 공백 제거
    if not url:
        continue  # 빈 라인은 건너뜁니다

    try:
        # 페이지 열기
        driver.get(url)

        time.sleep(5)

        # iframe 전환
        try:
            iframe = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "iframe#gib_frame"))
            )
            driver.switch_to.frame(iframe)

            # iframe 내부 텍스트 가져오기
            iframe_body = driver.find_element(By.TAG_NAME, "body")
            iframe_text = iframe_body.text.strip()

            # 이미지 링크를 가져오기 전에 텍스트가 있는지 확인
            img_links = []  # 기본값을 빈 배열로 설정
            if iframe_text == "":  # 텍스트가 없을 경우에만 이미지 링크 추출
                # iframe 내부 이미지 링크 가져오기 (중복 제거)
                img_elements = iframe_body.find_elements(By.TAG_NAME, "img")
                img_links_set = set()  # 중복 제거를 위한 set 사용
                for img in img_elements:
                    src = img.get_attribute("src")
                    if src:
                        img_links_set.add(src)  # set에 추가
                img_links = list(img_links_set)  # 중복 제거된 리스트 생성pyt

        except Exception as e:
            # iframe이 없으면 section > article에서 텍스트 추출
            iframe_text = ""
            img_links = []
            content_section = driver.find_element(By.CSS_SELECTOR, "section.section-content")
            article = content_section.find_element(By.CLASS_NAME, "view-content.view-detail")
            iframe_text = article.text.strip()

            # 이미지 링크 추출 (중복 제거)
            img_elements = article.find_elements(By.TAG_NAME, "img")
            img_links_set = set()  # 중복 제거를 위한 set 사용
            for img in img_elements:
                src = img.get_attribute("src")
                if src:
                    img_links_set.add(src)  # set에 추가
            img_links = list(img_links_set)  # 중복 제거된 리스트 생성

        # 마감일 정보 수집
        driver.switch_to.default_content()
        deadline = None
        due_type = None
        try:
            date_elements = driver.find_elements(By.CSS_SELECTOR, "dl.date .tahoma")
            if len(date_elements) > 1:  # 시작일과 마감일 둘 다 존재하는 경우
                deadline_text = date_elements[1].text.strip()  # 두 번째 <span class="tahoma">
                deadline_match = re.search(r"(\d{4}\.\s*\d{2}\.\s*\d{2})", deadline_text)
                if deadline_match:
                    deadline = deadline_match.group(1).replace(".", "-").replace(" ", "")  # 2024-12-07 형태로 변환
                    due_type = "날짜"  # 날짜 형식이면 due_type을 "날짜"로 설정

        except Exception as e:
            # deadline이 None일 경우 "상시채용"으로 설정
            print(f"[ERROR] 마감일 정보가 정의되지 않았습니다. {url}")
            error_count += 1
            error_types["<deadline is not defined>"] += 1
            due_type = "상시채용"  # deadline이 없으면 due_type은 "상시채용"으로 설정

        # 회사 이름 및 게시물 제목 수집
        company_name = None
        try:
            summary_section = driver.find_element(By.CLASS_NAME, "secReadSummary")
            company_name = summary_section.find_element(By.CLASS_NAME, "coName").text.strip()
            if not company_name:
                summary_section = driver.find_element(By.CLASS_NAME, "view-subtitle dev-wrap-subtitle")
        except Exception as e:
            # 회사 이름을 "를 소개해요" 이전 텍스트로 추출
            company_name = extract_company(iframe_text) if company_name == None else company_name

        post_title = None
        try:
            summary_section = driver.find_element(By.CLASS_NAME, "secReadSummary")
            # 기존 제목을 찾고 텍스트를 추출
            post_title = summary_section.find_element(By.CLASS_NAME, "sumTit").text.strip()

            # "닫기" 이후의 텍스트만 추출
            if "닫기" in post_title:
                post_title = post_title.split("닫기")[1].strip()
        except Exception as e:
            try:
                # 두 번째 시도: section class="view-title dev-wrap-title"에서 제목 추출
                title_section = driver.find_element(By.CSS_SELECTOR, "section.view-title.dev-wrap-title")
                post_title = title_section.text.strip()
            except Exception as e2:
                print(f"[ERROR] 게시물 제목이 정의되지 않았습니다. {url}")
                error_count += 1
                error_types["post_title_not_found"] += 1  # 게시물 제목을 찾을 수 없을 경우 에러 추가
                post_title = "N/A"  # 게시물 제목을 찾을 수 없으면 'N/A'로 설정

        # 텍스트 파일 및 이미지 URL 업로드
        if iframe_text:  # 텍스트가 비어있지 않으면 텍스트 파일을 생성하고 업로드
            filename = f"{uuid4()}.txt"  # UUID 기반 파일 이름 생성
            file_path = os.path.join(text_dir, filename)
            with open(file_path, "w", encoding="utf-8") as file:
                file.write(iframe_text)  # 텍스트 파일 저장

            # S3로 업로드
            s3_text_url = upload_to_s3(file_path, "t2jt", f"job/DE/sources/jobkorea/txt/{filename}")  # 텍스트 파일 업로드
        else:
            s3_text_url = None  # 텍스트가 없으면 s3_text_url은 None으로 설정

        # 이미지 다운로드 및 업로드
        image_urls = []
        for img_url in img_links:
            image_filename = f"{uuid4()}.jpg"  # UUID 기반 이미지 파일 이름 생성
            image_path = os.path.join(image_dir, image_filename)
            if download_image(img_url, image_path):
                image_url = upload_to_s3(image_path, "t2jt", f"job/DE/sources/jobkorea/images/{image_filename}")
                if image_url:
                    image_urls.append(image_url)  # 업로드한 이미지 URL을 리스트에 추가


        # DB에 저장할 데이터 준비
        notice_type = None
        if s3_text_url and not image_urls:
            notice_type = "text"
        elif not s3_text_url and image_urls:
            notice_type = "images"
        elif s3_text_url and image_urls:
            notice_type = "both"
   
        # 아래에 "removed_time": None,  # 삭제된 시간은 None으로 설정
        # DB에 저장할 데이터 준비
        data = {
            "create_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "update_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "removed_time": None,  # 삭제된 시간은 None으로 설정
            "site": "jobkorea",
            "job_title": "DE",
            "due_type": due_type if due_type else "상시채용",
            "due_date": deadline,
            "company": company_name,
            "post_title": post_title,
            "notice_type": notice_type,
            "org_url": url,
            "s3_text_url": s3_text_url,  # S3 URL을 삽입
            "s3_images_url": ", ".join(image_urls) if image_urls else None,  # 이미지 URL들을 ,로 연결하여 삽입
            "responsibility": None,  # 필요한 경우 추가 필드 추가
            "qualification": None,   # 필요한 경우 추가 필드 추가
            "preferential": None     # 필요한 경우 추가 필드 추가
        }


        # MySQL DB에 저장
        cursor.execute(insert_query, tuple(data.values()))
        db.commit()  # 데이터베이스에 커밋

        processed_count += 1  # 처리된 파일 수 증가

        log_status(url, "update", "done")
    except Exception as e:
        print(f"\n[ERROR] {url}을 DB에 업데이트하는 도중 에러가 발생했습니다.")
        print("\n")
        print("에러 사항은 아래와 같습니다.")
        print(e)
        print("\n")
        skipped_urls.append(url)
        error_count += 1
        logging.error(f"[ERROR] {url} 크롤링 실패: {e}")
        log_status(url, "update", "failed")

# removed_time이 NULL인 경우에만 업데이트하도록 추가
for removed_url in removed_urls:
    try:
        # removed_time이 NULL인 경우만 업데이트
        select_query = """
            SELECT removed_time FROM jobkorea WHERE org_url = %s
        """
        cursor.execute(select_query, (removed_url,))
        result = cursor.fetchone()
        
        # removed_time이 NULL인 경우에만 업데이트
        if result and result[0] is None:
            update_query = """
                UPDATE jobkorea
                SET removed_time = %s
                WHERE org_url = %s
            """
            removed_time = datetime.now().strftime("%Y-%m-%d")
            cursor.execute(update_query, (removed_time, removed_url))
            db.commit()
            print(f"[INFO] URL {removed_url}에 대해 removed_time이 {removed_time}으로 업데이트되었습니다.")
        else:
            print(f"[INFO] URL {removed_url}에 대해 removed_time이 이미 존재하므로 업데이트하지 않습니다.")
        log_status(url, "removed", "done")

        # MySQL DB에 저장
        cursor.execute(insert_query, tuple(data.values()))
        db.commit()  # 데이터베이스에 커밋
            
    except Exception as e:
        print(f"[ERROR] URL {removed_url}에 대해 removed_time 업데이트 중 오류 발생.")
        print(e)
        log_status(url, "removed", "failed")


# 웹 드라이버 종료
driver.quit()

# MySQL 연결 끊기
db.close()

# 작업이 완료되었음을 출력
print(f"[INFO] 처리된 총 개수: {processed_count}")
print(f"[INFO] 오류 개수: {error_count}")
for error_type, count in error_types.items():
    print(f"[INFO] {error_type}: {count}")
# print(f"건너뛴 URL들: {skipped_urls}")
