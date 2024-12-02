import boto3
from botocore.exceptions import NoCredentialsError

# 파일 이름
file_name = "../20241126.txt"  # 실제 파일 이름으로 변경

# S3 버킷 정보
bucket_name = "t2jt"
s3_file_path = "job/DE/sources/jobkorea/links/20241126.txt"  # 업로드 경로

# URL 정리 함수
def clean_url(url):
    return url.split('?')[0]  # '?' 이전 부분만 반환

# 파일 읽고 URL 정리 후 저장
def process_file(file_name):
    try:
        with open(file_name, "r", encoding="utf-8") as file:
            lines = file.readlines()  # 모든 줄 읽기
        
        # URL 정리
        cleaned_lines = [clean_url(line.strip()) for line in lines if line.strip()]

        # 정리된 URL을 같은 파일에 덮어쓰기
        with open(file_name, "w", encoding="utf-8") as file:
            for line in cleaned_lines:
                file.write(line + "\n")

        print(f"파일 '{file_name}'이 성공적으로 처리되었습니다!")
    except FileNotFoundError:
        print(f"파일 '{file_name}'을 찾을 수 없습니다.")
    except Exception as e:
        print(f"오류 발생: {e}")

# S3 업로드 함수
def upload_to_s3(local_file_path, bucket_name, s3_file_path):
    try:
        s3_client = boto3.client('s3')
        s3_client.upload_file(local_file_path, bucket_name, s3_file_path)
        print(f"파일이 S3에 성공적으로 업로드되었습니다: s3://{bucket_name}/{s3_file_path}")
    except NoCredentialsError:
        print("AWS 자격 증명 오류: 자격 증명이 없습니다.")
    except Exception as e:
        print(f"S3 업로드 중 오류 발생: {e}")

# 실행
process_file(file_name)  # 파일 정리
upload_to_s3(file_name, bucket_name, s3_file_path)  # S3에 업로드
