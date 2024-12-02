# 두 파일 경로 (파일명은 실제 파일 경로로 바꿔주세요)
file_yesterday = '20241126.txt'  # 어제 파일 경로
file_today = '20241127.txt'  # 오늘 파일 경로

# 파일에서 URL 추출하는 함수
def extract_urls_from_file(file_path):
    with open(file_path, 'r', encoding='utf-8') as file:
        lines = file.readlines()
        urls = set(line.strip() for line in lines if line.startswith('http'))  # URL만 추출
    return urls

# 두 파일에서 URL 추출
urls_yesterday = extract_urls_from_file(file_yesterday)
urls_today = extract_urls_from_file(file_today)

# 어제는 있었지만 오늘은 없는 URL 찾기
urls_only_in_yesterday = urls_yesterday - urls_today

# 결과 출력
print(f"어제는 있었지만 오늘은 없는 URL 수: {len(urls_only_in_yesterday)}")

