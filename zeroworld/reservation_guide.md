# 제로월드 예약 자동화 가이드

## 🎯 개요
제로월드 (강남점 등 다중 지점)의 방탈출 예약을 자동화하는 Python 스크립트입니다.

## 🛠️ 설치 및 설정

### 1. 필수 라이브러리 설치
```bash
pip3 install selenium requests beautifulsoup4
```

### 2. ChromeDriver 설치
```bash
# macOS (Homebrew)
brew install chromedriver

# 또는 수동 다운로드
# https://chromedriver.chromium.org/
```

### 3. 환경 설정
```python
# config.py 파일 생성
RESERVATION_CONFIG = {
    'target_date': '2025-08-18',  # YYYY-MM-DD 형식
    'target_time': '19:00',       # HH:MM 형식
    'theme_id': '1',              # 테마 ID
    'store': 'gangnam',           # 지점 선택 ('gangnam' 등)
    'check_interval': 30,         # 확인 주기 (초)
    'user_info': {
        'name': '홍길동',
        'phone': '010-1234-5678',
        'email': 'hong@example.com',
        'people_count': 4
    }
}

# 지점 설정 (STORE_CONFIGS)
STORE_CONFIGS = {
    'gangnam': {
        'name': '강남점',
        'base_url': 'https://gangnam.zeroworld.co.kr',
        'reservation_url': 'https://gangnam.zeroworld.co.kr/reservation'
    }
    # 다른 지점들 추가 가능
}
```

## 📋 사용 방법

### 1. 기본 사용법
```python
from zeroworld_reservation import ZeroWorldReservation
from datetime import datetime, timedelta

# 예약 시스템 초기화 (지점 지정)
reservation = ZeroWorldReservation(store='gangnam')

# 일주일 후 오후 7시 예약 시도
target_date = datetime.now() + timedelta(days=7)
result = reservation.make_reservation(
    date=target_date,
    target_time="19:00",
    theme_id="1",
    user_info={
        'name': '홍길동',
        'phone': '010-1234-5678',
        'people_count': 4  # email 필드는 실제 코드에서 사용되지 않음
    }
)

print(result)
```

### 2. 모니터링 모드
```python
# 주기적으로 확인하며 예약 가능할 때까지 대기
result = reservation.monitor_and_book(
    target_date=target_date,
    target_time="19:00",
    theme_id="1",
    user_info=user_info,
    check_interval=30  # 30초마다 확인
)
```

### 3. 페이지 구조 분석
```python
# 사이트 구조가 변경되었을 때 분석 실행
structure = reservation.analyze_page_structure()
print(json.dumps(structure, indent=2, ensure_ascii=False))
```

## 🔧 커스터마이징

### 1. 선택자 수정
사이트 구조가 변경되면 다음 메서드들의 선택자를 수정해야 합니다:

```python
def find_date_selector(self, target_date):
    # 실제 사이트의 날짜 선택자에 맞게 수정
    selectors = [
        f'[data-date="{date_str}"]',
        f'.calendar-day[data-value="{date_str}"]',
        # 추가 선택자들...
    ]
```

### 2. API 엔드포인트 수정
```python
def get_available_times(self, target_date, user_info=None):
    # 실제 사용되는 API 엔드포인트
    api_url = f"{self.base_url}/reservation/theme"
    # POST 요청으로 예약 가능한 시간 조회
```

## 🕵️ 사이트 분석 방법

### 1. 개발자 도구 사용
1. Chrome에서 F12 키로 개발자 도구 열기
2. Network 탭에서 예약 과정의 네트워크 요청 모니터링
3. Elements 탭에서 HTML 구조 분석

### 2. 중요 확인 사항
- **폼 구조**: 예약 폼의 action, method, 필드명 확인
- **AJAX 요청**: JavaScript로 처리되는 비동기 요청 패턴
- **인증 토큰**: CSRF 토큰이나 세션 관리 방식
- **캡챠**: reCAPTCHA나 기타 봇 방지 시스템
- **시간 형식**: 날짜/시간 데이터 전송 형식

### 3. 실제 분석 예시
```javascript
// 브라우저 콘솔에서 실행
// 1. 예약 관련 전역 변수 찾기
Object.keys(window).filter(key => 
    ['reservation', 'booking', 'calendar'].some(term => 
        key.toLowerCase().includes(term)
    )
);

// 2. AJAX 요청 감지
const originalFetch = window.fetch;
window.fetch = function(...args) {
    console.log('Fetch:', args);
    return originalFetch.apply(this, args);
};

// 3. 폼 구조 분석
Array.from(document.forms).map(form => ({
    action: form.action,
    method: form.method,
    fields: Array.from(form.elements).map(el => el.name)
}));
```

## 📊 예약 데이터 구조

제로월드 사이트에서 발견된 데이터 구조:
```json
{
    "times": {
        "1": [
            {
                "time": "10:00:00",
                "reservation": false
            },
            {
                "time": "19:00:00",
                "reservation": true
            }
        ]
    }
}
```

- `times`: 테마별 시간 슬롯 정보
- `time`: 시간 (HH:MM:SS 형식)
- `reservation`: true면 예약됨, false면 예약 가능

## 🤖 고급 자동화 기능

### 1. 다중 테마 모니터링
```python
def monitor_multiple_themes(self, target_date, target_time, theme_preferences, user_info):
    """여러 테마 중 먼저 예약 가능한 것으로 예약"""
    while True:
        for theme_id in theme_preferences:
            available_times = self.get_available_times(target_date, user_info)
            if target_time in available_times:
                return self.make_reservation(target_date, target_time, theme_id, user_info)
        time.sleep(30)
```

### 2. 스마트 시간 선택
```python
def find_best_time_slot(self, target_date, preferred_times):
    """선호 시간대 중 예약 가능한 시간 찾기"""
    available_times = self.get_available_times(target_date)
    
    for preferred_time in preferred_times:
        if preferred_time in available_times:
            return preferred_time
    
    return None
```

### 3. 알림 기능
```python
import smtplib
from email.mime.text import MIMEText

def send_notification(self, message):
    """예약 결과 이메일 알림"""
    msg = MIMEText(message, 'plain', 'utf-8')
    msg['Subject'] = '제로월드 예약 결과'
    msg['From'] = 'your_email@gmail.com'
    msg['To'] = 'recipient@gmail.com'
    
    # Gmail SMTP 설정 필요
    server = smtplib.SMTP('smtp.gmail.com', 587)
    server.starttls()
    server.login('your_email@gmail.com', 'app_password')
    server.send_message(msg)
    server.quit()
```

## 🛡️ 보안 및 안정성

### 1. 요청 제한
```python
import random

def add_random_delay(self):
    """무작위 지연으로 봇 탐지 회피"""
    delay = random.uniform(1, 3)
    time.sleep(delay)

def rotate_user_agent(self):
    """User-Agent 로테이션"""
    user_agents = [
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        # 더 많은 User-Agent 추가
    ]
    return random.choice(user_agents)
```

### 2. 에러 처리
```python
def safe_click(self, element):
    """안전한 클릭 (요소가 클릭 가능할 때까지 대기)"""
    try:
        WebDriverWait(self.driver, 10).until(
            EC.element_to_be_clickable(element)
        )
        element.click()
        return True
    except Exception as e:
        self.logger.error(f"클릭 실패: {e}")
        return False
```

### 3. 세션 관리
```python
def maintain_session(self):
    """세션 유지를 위한 주기적 요청"""
    heartbeat_url = f"{self.base_url}/api/heartbeat"
    try:
        self.session.get(heartbeat_url)
        self.logger.info("세션 갱신 완료")
    except:
        self.logger.warning("세션 갱신 실패")
```

## 🔍 문제 해결

### 자주 발생하는 문제들

1. **ChromeDriver 버전 불일치**
   ```bash
   # 자동 관리 도구 사용
   pip install webdriver-manager
   ```
   ```python
   from webdriver_manager.chrome import ChromeDriverManager
   service = Service(ChromeDriverManager().install())
   ```

2. **요소를 찾을 수 없음**
   ```python
   # 명시적 대기 사용
   element = WebDriverWait(driver, 20).until(
       EC.presence_of_element_located((By.ID, "element-id"))
   )
   ```

3. **CSRF 토큰 처리**
   ```python
   def get_csrf_token(self):
       token_element = self.driver.find_element(By.NAME, "csrf_token")
       return token_element.get_attribute("value")
   ```

4. **JavaScript 로딩 완료 대기**
   ```python
   def wait_for_page_load(self):
       WebDriverWait(self.driver, 30).until(
           lambda driver: driver.execute_script("return jQuery.active == 0")
       )
   ```

## 📈 성능 최적화

### 1. 브라우저 최적화
```python
chrome_options = Options()
chrome_options.add_argument('--disable-extensions')
chrome_options.add_argument('--disable-gpu')
chrome_options.add_argument('--disable-dev-shm-usage')
chrome_options.add_argument('--no-sandbox')
chrome_options.add_argument('--disable-images')  # 이미지 로딩 비활성화
```

### 2. 메모리 관리
```python
def periodic_cleanup(self):
    """주기적 메모리 정리"""
    if self.driver:
        self.driver.delete_all_cookies()
        self.driver.execute_script("window.localStorage.clear();")
```

## 📞 지원 및 문의

### 개발자 연락처
- 이 스크립트에 대한 문의사항이 있으시면 GitHub Issues를 활용해주세요
- 법적 문제나 사이트 정책 위반 시 즉시 사용을 중단하세요

### 추가 리소스
- [Selenium 공식 문서](https://selenium-python.readthedocs.io/)
- [Python Requests 문서](https://requests.readthedocs.io/)
- [웹 스크래핑 윤리 가이드](https://blog.apify.com/web-scraping-ethics/)

---

**⚠️ 면책 조항**: 이 스크립트는 교육 목적으로만 제공됩니다. 실제 사용으로 인한 모든 책임은 사용자에게 있으며, 사이트 이용약관 위반이나 법적 문제에 대해서는 개발자가 책임지지 않습니다.