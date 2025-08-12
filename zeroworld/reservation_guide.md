# 제로월드 예약 자동화 가이드

## 🎯 개요
제로월드 (강남점, 홍대점) 방탈출 예약을 자동화하는 Python 스크립트입니다.

## ✨ 주요 특징
- **다중 날짜 지원**: 여러 날짜를 우선순위별로 자동 시도
- **시간 구간 예약**: 원하는 시간대 내에서 자동 선택
- **날짜별 독립 테마 매핑**: 각 날짜별로 다른 테마 ID 자동 처리
- **실시간 모니터링**: 주기적으로 예약 가능 시간 확인
- **안정적인 테마 관리**: 테마명 기반으로 동적 ID 매칭

## 🛠️ 설치 및 설정

### 1. 필수 라이브러리 설치
```bash
pip3 install selenium requests
```

### 2. ChromeDriver 설치
```bash
# macOS (Homebrew)
brew install chromedriver

# 또는 수동 다운로드
# https://chromedriver.chromium.org/
```

### 3. 환경 설정 (config.py)
```python
STORE_CONFIGS = {
    'gangnam': {
        'name': '제로월드 강남점',
        'base_url': 'https://zerogangnam.com',
        'reservation_url': 'https://zerogangnam.com/reservation'
    },
    'hongdae': {
        'name': '제로월드 홍대점',
        'base_url': 'https://zerohongdae.com',
        'reservation_url': 'https://zerohongdae.com/reservation'
    }
}

RESERVATION_CONFIG = {
    'store': 'hongdae',               # 'gangnam' 또는 'hongdae'
    'target_dates': [                 # 여러 날짜 지원 (우선순위 순)
        '2025-08-24',
        '2025-08-25',
        '2025-08-26'
    ],
    'time_range': {                  # 원하는 시간 구간
        'start': '11:00',            # 시작 시간 (HH:MM)
        'end': '21:00'               # 종료 시간 (HH:MM)
    },
    'theme': '층간소음',               # 테마명
    'check_interval': 30,            # 확인 주기 (초)
    'user_info': {
        'name': '홍길동',
        'phone': '010-1234-5678',
        'people_count': 4
    }
}
```

## 📋 사용 방법

### 1. 간단 실행
```bash
cd zeroworld
python3 zeroworld_reservation.py
```

### 2. 실행 결과 예시
```
INFO:__main__:예약 시스템 초기화: 제로월드 홍대점
테마 정보 로드 중...
테마 정보 로드 시도 1/3...
대상 테마: '층간소음'
현재 사용 가능한 테마: ['층간소음', 'NOX', '타임머신']
📅 3개 날짜에 대해 30초마다 확인합니다...

[1/3] 📅 예약 확인: 2025-08-24 11:00-21:00 (테마: 층간소음)
INFO:__main__:예약 확인: 2025-08-24 11:00-21:00 (테마: 층간소음)
INFO:__main__:테마명 변환: '층간소음' -> ID '61' (2025-08-24)
INFO:__main__:테마 '층간소음'에서 0개의 예약 가능한 시간 발견: []
❌ 예약 실패: 2025-08-24 - 테마 '층간소음'에서 예약 가능한 시간 없음

[2/3] 📅 예약 확인: 2025-08-25 11:00-21:00 (테마: 층간소음)
INFO:__main__:테마명 변환: '층간소음' -> ID '60' (2025-08-25)
INFO:__main__:테마 '층간소음'에서 2개의 예약 가능한 시간 발견: ['14:30', '18:45']
✅ 예약 성공: 2025-08-25 14:30 - 예약이 완료되었습니다
```

### 3. 프로그래밍 방식 사용
```python
from zeroworld_reservation import ZeroWorldReservation
from datetime import datetime

# 예약 시스템 초기화
reservation = ZeroWorldReservation(store='hongdae')

# 특정 날짜 예약 시도
target_date = datetime(2025, 8, 25)
time_range = {'start': '14:00', 'end': '20:00'}

result = reservation.check_and_book(
    target_date=target_date,
    time_range=time_range,
    theme_name='층간소음',
    user_info={
        'name': '김동원',
        'phone': '010-7487-9901',
        'people_count': 2
    }
)

if result["success"]:
    print(f"✅ 예약 성공: {result['time']} - {result['message']}")
else:
    print(f"❌ 예약 실패: {result['message']}")
```

## ⏰ 주요 특징 상세

### 1. 날짜별 독립 테마 매핑
각 날짜마다 테마 ID가 다를 수 있습니다. 시스템이 자동으로 처리합니다.

```
2025-08-24: '층간소음' -> ID '61'
2025-08-25: '층간소음' -> ID '60' 
2025-08-26: '층간소음' -> ID '60'
```

### 2. 시간 구간 예약
원하는 시간대를 범위로 지정하면 해당 구간 내에서 가장 빠른 시간으로 자동 예약:

```python
'time_range': {
    'start': '14:00',    # 시작 시간
    'end': '20:00'       # 종료 시간
}

# 실행 시 자동 선택:
# 14:30, 18:45가 가능하면 → 14:30 선택 (더 빠른 시간)
```

### 3. 다중 날짜 우선순위 처리
```python
'target_dates': [
    '2025-08-24',  # 1순위 - 먼저 시도
    '2025-08-25',  # 2순위 - 1순위 실패 시
    '2025-08-26'   # 3순위 - 2순위 실패 시
]
```

### 4. 실시간 모니터링
```
📅 3개 날짜에 대해 30초마다 확인합니다...
[1/3] 📅 예약 확인: 2025-08-24 (실패)
[2/3] 📅 예약 확인: 2025-08-25 (실패)  
[3/3] 📅 예약 확인: 2025-08-26 (실패)
모든 날짜에서 예약 불가. 30초 후 다시 시도...

[1/3] 📅 예약 확인: 2025-08-24 (실패)
[2/3] 📅 예약 확인: 2025-08-25 (성공!) ← 예약 완료
```

## 🎭 테마 관리

### 1. 자동 테마 감지
- 시스템이 자동으로 사용 가능한 테마 목록을 가져옵니다
- 날짜별로 다른 테마 ID를 자동 매칭합니다
- 테마명만 설정하면 ID는 자동 처리됩니다

### 2. 지원하는 테마 (예시)
```
홍대점: '층간소음', 'NOX', '타임머신'
강남점: '미스터리 하우스', '공포의 병원' 등
```

## 🛠️ 설정 상세

### 1. 지점 설정
```python
'store': 'hongdae'  # 또는 'gangnam'
```

### 2. 시간 설정
```python
'check_interval': 30  # 확인 주기 (초)
                      # 30 = 30초마다 확인
                      # 60 = 1분마다 확인
```

### 3. 사용자 정보
```python
'user_info': {
    'name': '김동원',        # 예약자명
    'phone': '010-1234-5678', # 전화번호
    'people_count': 2         # 인원수
}
```

## 📊 시스템 구조

### 1. 핵심 기능
```python
ZeroWorldReservation()
├── get_available_times_for_theme()  # 예약 가능 시간 조회
├── check_and_book()                 # 예약 확인 및 시도
├── make_reservation()               # 실제 예약 실행
└── extract_theme_info()             # 테마 정보 추출
```

### 2. 데이터 구조
```python
# 날짜별 테마 매핑
date_theme_mappings = {
    '2025-08-24': {'층간소음': '61', 'NOX': '62'},
    '2025-08-25': {'층간소음': '60', 'NOX': '61'},
    '2025-08-26': {'층간소음': '60', 'NOX': '61'}
}
```

## 🔍 문제 해결

### 자주 발생하는 문제

1. **ChromeDriver 설치 문제**
   ```bash
   # macOS
   brew install chromedriver
   
   # 또는 webdriver-manager 사용
   pip3 install webdriver-manager
   ```

2. **테마를 찾을 수 없음**
   ```
   ValueError: 테마를 찾을 수 없습니다: '층간소음'. 
   2025-08-24에 사용 가능한 테마: ['NOX', '타임머신']
   ```
   → config.py에서 정확한 테마명으로 수정

3. **예약 페이지 로딩 실패**
   ```
   INFO:__main__:⚠️ 테마 정보 로드 실패. API 응답을 확인해주세요.
   ```
   → 네트워크 연결 및 사이트 상태 확인

4. **Selenium 오류**
   ```bash
   # Chrome 업데이트 후 ChromeDriver도 업데이트
   brew upgrade chromedriver
   ```

### 로그 이해하기

**성공적인 실행:**
```
INFO:__main__:예약 시스템 초기화: 제로월드 홍대점
INFO:__main__:테마명 변환: '층간소음' -> ID '61' (2025-08-24)
INFO:__main__:테마 '층간소음'에서 2개의 예약 가능한 시간 발견: ['14:30', '18:45']
✅ 예약 성공: 2025-08-25 14:30 - 예약이 완료되었습니다
```

**예약 불가 상황:**
```
INFO:__main__:테마 '층간소음'에서 0개의 예약 가능한 시간 발견: []
❌ 예약 실패: 2025-08-24 - 테마 '층간소음'에서 예약 가능한 시간 없음
```

## 📋 체크리스트

실행 전 확인사항:
- [ ] ChromeDriver 설치됨
- [ ] config.py 설정 완료
- [ ] 지점 정보 정확함 ('hongdae' 또는 'gangnam')
- [ ] 테마명 정확함
- [ ] 날짜 형식 올바름 ('YYYY-MM-DD')
- [ ] 사용자 정보 입력 완료

---

**⚠️ 주의사항**: 
- 이 도구는 개인적 용도로만 사용하세요
- 과도한 요청으로 서버에 부하를 주지 마세요
- 사이트 이용약관을 준수하세요