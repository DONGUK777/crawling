import boto3
import csv


# S3 클라이언트 설정
s3_client = boto3.client('s3')

def list_s3_files(bucket_name, prefix):
    """S3 버킷에서 지정된 prefix(경로)에 있는 모든 파일 목록을 반환"""
    files = []
    continuation_token = None  # 첫 번째 호출에서는 None으로 초기화
    while True:
        # ContinuationToken이 None일 때는 제거하거나 빈 문자열을 넘김
        params = {
            'Bucket': bucket_name,
            'Prefix': prefix
        }
        
        if continuation_token:
            params['ContinuationToken'] = continuation_token
        
        response = s3_client.list_objects_v2(**params)
        
        # 파일 목록을 리스트에 추가
        files.extend([content['Key'] for content in response.get('Contents', [])])
        
        # 다음 페이지 토큰을 갱신
        continuation_token = response.get('NextContinuationToken')
        
        if not continuation_token:  # 더 이상 토큰이 없으면 반복 종료
            break
    
    return files



def extract_text_from_s3_file(bucket_name, file_key, keyword_groups):
    """S3에서 파일을 읽고 텍스트 추출"""
    response = s3_client.get_object(Bucket=bucket_name, Key=file_key)
    file_content = response['Body'].read().decode('utf-8')
    
    extracted_sections = {}
    
    # 각 섹션에 대해 텍스트 추출
    for group in keyword_groups:
        section_name = group['section_name']
        start_keywords = group['start_keywords']
        end_keywords = group['end_keywords']
        
        start_index = None
        end_index = None
        section_text = ""
        
        # 시작 키워드 찾아서 섹션 시작
        for start in start_keywords:
            start_index = file_content.find(start)
            if start_index != -1:
                break
        
        # 끝 키워드 찾아서 섹션 종료
        if start_index != -1:
            for end in end_keywords:
                end_index = file_content.find(end, start_index)
                if end_index != -1:
                    break
        
        if start_index != -1 and end_index != -1:
            section_text = file_content[start_index:end_index].strip()
        
        extracted_sections[section_name] = section_text
    
    return extracted_sections

def process_s3_files(bucket_name, prefix, keyword_groups, output_csv):
    """S3 버킷 내 모든 파일을 처리하고 결과를 CSV로 저장"""
    # S3 버킷에서 텍스트 파일 목록 가져오기
    files = list_s3_files(bucket_name, prefix)
    
    # CSV 파일 작성
    with open(output_csv, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(['파일명', '주요 업무', '자격요건', '우대사항'])
        
        # 각 파일에 대해 텍스트 추출 및 저장
        for file_key in files:
            if file_key.endswith('.txt'):  # .txt 파일만 처리
                sections = extract_text_from_s3_file(bucket_name, file_key, keyword_groups)
                writer.writerow([file_key, sections.get('주요업무', ''), sections.get('자격요건', ''), sections.get('우대사항', '')])

# 키워드 그룹 정의
keyword_groups = [
    {
        "section_name": "주요업무",
        "start_keywords": [
            "합류하면 함께 할 업무예요", "이런 일을 함께하고 싶습니다.", "담당 업무는 다음과 같습니다.", "[담당업무]", "[담당 업무]", "[담당업무] ", "이런 업무를 해요", "담당업무 내용",
            "함께 담당하게 될 업무입니다", "Key Responsibilities", "담당 업무", "담당업무", "주요업무", "주요 업무", "[주요 업무]", "[주요업무]", "# 담당업무 ",
            "  [우리는 이런일을 합니다]", "담당업무 ", " 담당업무", "담당 업무 ", " 담당 업무", "  【업무소개】 이러한 일을 해요", "주요 업무: ", "이런 업무를 해요 [주요 업무]",
            "직무상세", "[ 업무 안내 ]", "업무 내용:", " 업무 내용 ", "직무소개",
        ],
        "end_keywords": [
            "자격요건", "자격 요건", "필수자격", "필수 자격", "필요 역량", "필요역량", "Required Qualifications", "자격 요건:", "필요역량 및 경험", "기술스택",
            "Bigdata Engineer로 이런 분이 필요합니다", "이런 분과 함께하고 싶습니다.", "이런 분들을 찾고 있어요", "필요역량 ", "  【기술스택】 이러한 툴을 활용해요",
            "이런 역량을 가지신 분을 찾습니다.", "이런 분과 함께하고 싶어요", "[자격요건]", "[자격 요건]", "# 자격요건", "[우리는 이런사람을 원합니다]", "  자격요건",
            "이런 자격을 갖춘 분을 찾고 있어요 [자격 요건]", "[필수 기술]", "필수사항", "지원자격", "지원 자격", "지원자격 ","[ 필수(자격) 조건 ]", "경험/역량 ",
            "[필수 경험과 역량]", "지원자격(필수)", "필수 경험과 역량 ", "자격요건 ", "[필수자격요건]", "필요 자격 및 기술 ", "[우대사항] ", "[우대사항]",
            "우대사항", "우대 사항", "우대 요건", "우대요건", "이런 분이면 더 좋아요", "[우대사항]", "[우대 사항]", "[우대 요건]", "[우대요건]", "# 우대사항 ", " 우대조건",
            "  【자격요건】 이러한 분을 찾고 있어요", "우대 사항:", "이런 분이 오시면 좋아요 [우대사항]", "Benefits ", "우대경험/역량", " 지원자격",
            "스킬", "모집 강의 주제 예시 (교안 및 교육 제공 / 일부만 강의 가능)", "개발 환경", "[모집절차]", "학력 및 경력", "기타 사항", " [ 근무 장소 ] ",
            "경력/기술 요건:", "우대사항 ", "[모집 절차]", "자격요건  ", "[Key Responsibilities]", "이런 조건에서 근무할 예정이에요", "청주본사",
            "[기본조건]", "기타사항", "[지원 및 진행 절차]", "  [자격 요건]", "[우대조건]", " 복리후생", "저희가 우대하는 분들은 :  ", "근무지",
            "●  요구 경험", "■ 근무시간", "자격사항", " [이런 경험이 있으시면 더욱 좋아요]", " [꼭 확인해 주세요!]", "□ 경력 요구사항", "□ 우대사항",
            "[경력] 경력 3년 이내", "[핵심역량 및 기술]",
        ]
    },
    {
        "section_name": "자격요건",
        "start_keywords": [
            "자격요건", "자격 요건", "필수자격", "필수 자격", "필요 역량", "필요역량", "Required Qualifications", "[우리는 이런사람을 원합니다]", "기술스택",
            "Bigdata Engineer로 이런 분이 필요합니다", "이런 분과 함께하고 싶습니다.", "이런 분들을 찾고 있어요", "# 자격요건", "자격 요건:", "필요역량 및 경험",
            "이런 역량을 가지신 분을 찾습니다.", "이런 분과 함께하고 싶어요", "[자격요건]", "[자격 요건]", "필요역량 ", "  【자격요건】 이러한 분을 찾고 있어요",
            "이런 자격을 갖춘 분을 찾고 있어요 [자격 요건]", "[필수 기술]", "필수사항", "지원 자격", "[ 필수(자격) 조건 ]", "경험/역량 ", "지원자격 ", "지원자격",
            "  자격요건", "[필수 경험과 역량]", "지원자격(필수)", "필수 경험과 역량 ", "자격요건 ", "[필수자격요건]", "필요 자격 및 기술 ", "자격요건  ", "[Key Responsibilities]",
            "[기본조건]", "  [자격 요건]", "●  요구 경험", "자격사항", "□ 경력 요구사항", "[핵심역량 및 기술]",
        ],
        "end_keywords": [
            "합류하면 함께 할 업무예요", "이런 일을 함께하고 싶습니다.", "담당 업무는 다음과 같습니다.", "담당업무 내용", "  [우리는 이런일을 합니다]", "[담당업무] ",
            "함께 담당하게 될 업무입니다", "Key Responsibilities", "담당 업무", "담당업무", "주요업무", "주요 업무", "[주요 업무]", "[주요업무]","# 담당업무 ",
            "담당업무 ", " 담당업무", "담당 업무 ", " 담당 업무", "  【업무소개】 이러한 일을 해요", "주요 업무: ", "이런 업무를 해요 [주요 업무]", "[ 업무 안내 ]",
            "업무 내용:", " 업무 내용 ", "Project Manager", "[우대조건]", "저희가 우대하는 분들은 :  ",
            "우대사항", "우대 사항", "우대 요건", "우대요건", "이런 분이면 더 좋아요", "[우대사항]", "[우대 사항]", "[우대 요건]", "[우대요건]", "# 우대사항 ",
            "  【우대사항】 이러한 분이면 더욱 좋아요", "우대 사항:", "이런 분이 오시면 좋아요 [우대사항]", "Benefits ", "우대경험/역량", " 우대조건",
            "근무시작일", "스킬", "[급여 조건]", "Place of Work ", "[기타]", "[ 제출서류 ]", "직무상세", "전형 절차", "전형절차", "기타 사항", "기타사항",
            "드론(조종) 촬영 보조", "경력/기술 요건:", "우대사항 ", "환경안전", "필요역량", "[모집 절차]", "우대사항  ", "우대사항-", "[지원 및 진행 절차]",
            " 복리후생", "근무시간", "근무지", "3. 투입시기", "■ 근무시간", "수행업무", "( 15명 )"," [이런 경험이 있으시면 더욱 좋아요]", " [꼭 확인해 주세요!]",
            "□ 우대사항", "□ 직무상세", "[우대사항]", "우대 사항",
        ]
    },
    {
        "section_name": "우대사항",
        "start_keywords": [
            "우대사항", "우대 사항", "우대 요건", "우대요건", "이런 분이면 더 좋아요", "[우대사항]", "[우대 사항]", "[우대 요건]", "[우대요건]", "# 우대사항 ", "  【우대사항】 이러한 분이면 더욱 좋아요", "우대 사항:",
            "이런 분이 오시면 좋아요 [우대사항]", "Benefits ", "우대경험/역량", " 우대조건", "우대사항 ", "우대사항-", "[우대조건]", "저희가 우대하는 분들은 :  ",
            " [이런 경험이 있으시면 더욱 좋아요]", "□ 우대사항", "[우대사항]",
        ],
        "end_keywords": [
            "합류하면 함께 할 업무예요", "이런 일을 함께하고 싶습니다.", "담당 업무는 다음과 같습니다.", "[담당업무]", "[담당 업무]", "# 담당업무 ", "담당업무 내용", "[담당업무] ",
            "함께 담당하게 될 업무입니다", "Key Responsibilities", "담당 업무", "담당업무", "주요업무", "주요 업무", "[주요 업무]", "[주요업무]", "  [우리는 이런일을 합니다]",
            "담당업무 ", " 담당업무", "담당 업무 ", " 담당 업무", "  【업무소개】 이러한 일을 해요", "주요 업무: ", "이런 업무를 해요 [주요 업무]", " 업무 내용 ",
            "직무상세", "[ 업무 안내 ]", "업무 내용:", "지원자격(필수)", "필수 경험과 역량 ", "자격요건 ", "[필수자격요건]", "필요 자격 및 기술 ",
            "자격요건", "자격 요건", "필수자격", "필수 자격", "필요 역량", "필요역량", "Required Qualifications", "필요역량 및 경험", "기술스택", "[필수 기술]",
            "필수사항", "지원 자격", "[ 필수(자격) 조건 ]", "경험/역량", "지원자격 ", "  자격요건", "[필수 경험과 역량]", "자격요건  ",
            "Bigdata Engineer로 이런 분이 필요합니다", "이런 분과 함께하고 싶습니다.", "이런 기술이 필요해요", "[우리는 이런사람을 원합니다]", "이런 자격을 갖춘 분을 찾고 있어요 [자격 요건]",
            "이런 역량을 가지신 분을 찾습니다.", "이런 분과 함께하고 싶어요", "[자격요건]", "[자격 요건]", "근무지", "# 자격요건","  【자격요건】 이러한 분을 찾고 있어요",
            "전형절차", "이런 조건에서 근무할 예정이에요", "○명", "근무조건", "스킬", "  【업무방향】 이러한 경험도 할 수 있어요", "혜택:", "혜택 및 복지", "기타사항",
            "제출서류", "▶ 지원서는 이렇게 작성하시면 좋아요", "[혜택 및 복지]", "지원자격", "측정", "기타 사항", "경력/기술 요건:", "●  요구 경험",
            "-----------------------------------------------------------------------", "[채용 전형 안내]", "BAT에 합류하는 여정", "기타 참고 사항", "Video Platform Team은 이런 팀입니다",
            "TSS > 기술컨설팅팀", "전형 절차 ", "전형 절차", "0명 ", "0명", "Full Stack Developer", "[모집 절차]", "[Key Responsibilities]", "[Application]",
            "○기타사항", "[근무 조건]", "[기본조건]", "기타사항 ㆍ사원~대리 직급 채용 희망", "[지원 및 진행 절차]", "  [자격 요건]", "재무팀 정규직", "지원 전 확인 부탁드립니다",
            "근무기간 : 6개월 (당사자 간 협의에 따라 연장 가능) / 인턴으로 3개월 근무 후 정규직 전환 평가", " 복리후생", "근무시간", "근무지", "■ 근무시간", "수행업무",
            "□ 기업문화 ", "자격사항", "근무조건 및 지원방법", " [꼭 확인해 주세요!]", "□ 경력 요구사항", "□ 직무상세", "[핵심역량 및 기술]",
        ]
    }
]

# S3 버킷과 결과 CSV 파일 지정
bucket_name = 't2jt'
prefix = 'job/DE/sources/jobkorea/txt/'  # 경로 수정
output_csv = 'division.csv'

# S3 버킷 내 파일 처리 및 결과 CSV 저장
process_s3_files(bucket_name, prefix, keyword_groups, output_csv)