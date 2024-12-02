import pandas as pd
import pymysql
from datetime import datetime

# CSV 파일 읽기
df = pd.read_csv('division.csv')

# NaN 값을 None으로 변환 (MySQL에서 NULL로 처리)
df = df.where(pd.notna(df), None)

# MySQL 연결
conn = pymysql.connect(
    host='43.201.40.223',          # AWS 퍼블릭 IP
    user='user',                   # MySQL 사용자
    password='1234',               # MySQL 비밀번호
    database='testdb',             # 데이터베이스 이름
    charset='utf8mb4'
)
cursor = conn.cursor()

for index, row in df.iterrows():
    # '파일명' 컬럼 앞에 's3://t2jt/'를 붙여서 업데이트
    full_s3_url = "s3://t2jt/" + row['파일명']

    # 현재 시간 초단위까지 생성
    current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    # '파일명'과 's3_text_url'이 같은 값을 가진 행을 업데이트
    cursor.execute("""
        UPDATE jobkorea
        SET update_time = %s, responsibility = %s, qualification = %s, preferential = %s
        WHERE s3_text_url = %s
    """, (current_time, row['주요 업무'], row['자격요건'], row['우대사항'], full_s3_url))

# 변경 사항 커밋
conn.commit()

# 연결 종료
cursor.close()
conn.close()
