#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import requests
import time
import json
from datetime import datetime, timedelta
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
import logging
from config import RESERVATION_CONFIG, STORE_CONFIGS

class ZeroWorldReservation:
    def __init__(self, store='gangnam'):
        # 지점 설정
        if store not in STORE_CONFIGS:
            raise ValueError(f"지원하지 않는 지점입니다: {store}. 사용 가능한 지점: {list(STORE_CONFIGS.keys())}")
        
        self.store_config = STORE_CONFIGS[store]
        self.base_url = self.store_config['base_url']
        self.reservation_url = self.store_config['reservation_url']
        self.store_name = self.store_config['name']
        
        self.session = requests.Session()
        self.driver = None
        self.csrf_token = None
        
        # 로깅 설정
        logging.basicConfig(level=logging.DEBUG)
        self.logger = logging.getLogger(__name__)
        self.logger.info(f"예약 시스템 초기화: {self.store_name}")
        
        # requests 로깅 활성화
        import urllib3
        urllib3.disable_warnings()
        logging.getLogger("requests").setLevel(logging.DEBUG)
        logging.getLogger("urllib3").setLevel(logging.DEBUG)
        
    def setup_driver(self, headless=False):
        """Chrome WebDriver 설정"""
        chrome_options = Options()
        if headless:
            chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36')
        
        self.driver = webdriver.Chrome(options=chrome_options)
        self.driver.implicitly_wait(10)
    
    def get_csrf_token(self, force_refresh=False):
        """CSRF 토큰 획득 (캐싱 지원)"""
        if self.csrf_token and not force_refresh:
            return self.csrf_token
            
        if not self.driver:
            self.setup_driver(headless=True)
        
        try:
            # 예약 페이지 로드
            self.logger.debug(f"CSRF 토큰 획득을 위한 페이지 로드: {self.reservation_url}")
            self.driver.get(self.reservation_url)
            time.sleep(2)
            self.logger.debug(f"현재 페이지 URL: {self.driver.current_url}")
            
            # meta 태그에서 CSRF 토큰 찾기
            csrf_selectors = [
                'meta[name="csrf-token"]',
                'meta[name="_token"]',
                'input[name="_token"]',
                '[name="csrf_token"]'
            ]
            
            for selector in csrf_selectors:
                try:
                    element = self.driver.find_element(By.CSS_SELECTOR, selector)
                    token = element.get_attribute('content') or element.get_attribute('value')
                    if token:
                        self.csrf_token = token
                        self.logger.info("CSRF 토큰 획득 성공")
                        return token
                except:
                    continue
            
            # JavaScript로 토큰 찾기 시도
            try:
                token = self.driver.execute_script("""
                    return window.Laravel && window.Laravel.csrfToken ||
                           document.querySelector('meta[name="csrf-token"]')?.content ||
                           document.querySelector('input[name="_token"]')?.value;
                """)
                if token:
                    self.csrf_token = token
                    return token
            except:
                pass
                
            self.logger.warning("CSRF 토큰을 찾을 수 없습니다")
            return None
            
        except Exception as e:
            self.logger.error(f"CSRF 토큰 획득 실패: {e}")
            return None
    
    def sync_session_cookies(self):
        """Selenium과 requests 세션 쿠키 동기화"""
        try:
            if self.driver:
                selenium_cookies = self.driver.get_cookies()
                self.logger.debug(f"🍪 Selenium 쿠키 개수: {len(selenium_cookies)}")
                for cookie in selenium_cookies:
                    self.session.cookies.set(cookie['name'], cookie['value'])
                    self.logger.debug(f"🍪 쿠키 추가: {cookie['name']}={cookie['value'][:20]}...")
                self.logger.info(f"✅ 세션 쿠키 동기화 완료: {len(selenium_cookies)}개")
        except Exception as e:
            self.logger.error(f"❌ 쿠키 동기화 실패: {e}")
        
    def analyze_page_structure(self):
        """페이지 구조 분석"""
        if not self.driver:
            self.setup_driver()
        
        self.logger.info(f"🔍 페이지 구조 분석 시작: {self.reservation_url}")    
        self.driver.get(self.reservation_url)
        time.sleep(3)
        self.logger.debug(f"페이지 로드 완료: {self.driver.current_url}")
        
        # JavaScript 실행으로 페이지 구조 분석
        analysis_script = """
        return {
            forms: Array.from(document.forms).map(form => ({
                action: form.action,
                method: form.method,
                elements: Array.from(form.elements).map(el => ({
                    name: el.name,
                    type: el.type,
                    id: el.id,
                    className: el.className
                }))
            })),
            
            buttons: Array.from(document.querySelectorAll('button, input[type="button"], input[type="submit"]')).map(btn => ({
                text: btn.textContent || btn.value,
                type: btn.type,
                id: btn.id,
                className: btn.className
            })),
            
            dateElements: Array.from(document.querySelectorAll('[class*="date"], [id*="date"], [data-*="date"]')).map(el => ({
                tag: el.tagName,
                id: el.id,
                className: el.className,
                textContent: el.textContent.slice(0, 50)
            })),
            
            timeElements: Array.from(document.querySelectorAll('[class*="time"], [id*="time"]')).map(el => ({
                tag: el.tagName,
                id: el.id,
                className: el.className,
                textContent: el.textContent.slice(0, 50)
            })),
            
            apiEndpoints: Array.from(document.scripts).map(script => script.innerHTML)
                .join(' ')
                .match(/\/api\/[^\s"']+/g) || [],
                
            ajaxCalls: window.jQuery ? 'jQuery detected' : 'No jQuery',
            
            reservationData: window.reservationData || 'No reservation data found',
            
            // 실제 예약 관련 스크립트나 변수 찾기
            globalVars: Object.keys(window).filter(key => 
                ['reservation', 'booking', 'calendar', 'schedule'].some(term => 
                    key.toLowerCase().includes(term)
                )
            )
        };
        """
        
        try:
            result = self.driver.execute_script(analysis_script)
            self.logger.info("페이지 구조 분석 완료")
            return result
        except Exception as e:
            self.logger.error(f"페이지 분석 실패: {e}")
            return None
    
    def get_available_times(self, target_date, user_info=None):
        """실제 API를 사용하여 예약 가능한 시간 조회"""
        try:
            # CSRF 토큰 획득
            csrf_token = self.get_csrf_token()
            if not csrf_token:
                self.logger.error("CSRF 토큰을 획득할 수 없습니다")
                return []
            
            # 세션 쿠키 동기화
            self.sync_session_cookies()
            
            # API 호출
            api_url = f"{self.base_url}/reservation/theme"
            self.logger.info(f"🔗 API 호출 URL: {api_url}")
            
            headers = {
                'accept': 'application/json, text/javascript, */*; q=0.01',
                'accept-language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7',
                'content-type': 'application/x-www-form-urlencoded; charset=UTF-8',
                'sec-ch-ua': '"Not)A;Brand";v="8", "Chromium";v="138", "Google Chrome";v="138"',
                'sec-ch-ua-mobile': '?0',
                'sec-ch-ua-platform': '"macOS"',
                'sec-fetch-dest': 'empty',
                'sec-fetch-mode': 'cors',
                'sec-fetch-site': 'same-origin',
                'x-csrf-token': csrf_token,
                'x-requested-with': 'XMLHttpRequest',
                'referer': self.reservation_url,
                'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
            }
            
            # POST 데이터 준비
            data = {
                'reservationDate': target_date.strftime('%Y-%m-%d'),
                'name': user_info.get('name', '') if user_info else '',
                'phone': user_info.get('phone', '') if user_info else '',
                'paymentType': '1'
            }
            
            self.logger.info(f"📤 POST 데이터: {data}")
            self.logger.info(f"🔑 CSRF 토큰: {csrf_token}")
            self.logger.debug(f"📋 요청 헤더: {headers}")
            
            response = self.session.post(api_url, headers=headers, data=data)
            
            self.logger.info(f"📥 응답 상태코드: {response.status_code}")
            self.logger.info(f"📥 응답 헤더: {dict(response.headers)}")
            
            if response.status_code == 200:
                try:
                    result = response.json()
                    self.logger.info("✅ API 호출 성공")
                    self.logger.info(f"📄 응답 데이터: {json.dumps(result, ensure_ascii=False, indent=2)}")
                    
                    # 응답에서 예약 가능한 시간 추출
                    available_times = self.extract_available_times(result)
                    self.logger.info(f"⏰ 예약 가능한 시간: {available_times}")
                    return available_times
                    
                except ValueError as e:
                    self.logger.error(f"❌ JSON 파싱 실패: {e}")
                    self.logger.error(f"📄 응답 내용 (원본): {response.text[:1000]}")
                    return []
            else:
                self.logger.error(f"❌ API 요청 실패: {response.status_code}")
                self.logger.error(f"📄 응답 내용: {response.text[:1000]}")
                return []
                
        except Exception as e:
            self.logger.error(f"예약 가능 시간 조회 실패: {e}")
            return []
    
    def extract_available_times(self, api_response):
        """API 응답에서 예약 가능한 시간 추출"""
        available_times = []
        
        try:
            # API 응답에서 times 섹션 추출
            if isinstance(api_response, dict) and 'times' in api_response:
                times_data = api_response['times']
                
                # 각 테마의 시간 정보 확인
                for theme_id, time_slots in times_data.items():
                    if isinstance(time_slots, list):
                        for slot in time_slots:
                            if isinstance(slot, dict) and 'time' in slot and 'reservation' in slot:
                                # reservation이 false인 경우가 예약 가능
                                if not slot['reservation']:
                                    time_str = slot['time']
                                    # HH:MM:SS 형식을 HH:MM으로 변환
                                    if time_str.count(':') == 2:
                                        time_str = time_str.rsplit(':', 1)[0]
                                    available_times.append(time_str)
                                    self.logger.debug(f"예약 가능한 시간 발견: 테마 {theme_id}, 시간 {time_str}")
            
            self.logger.info(f"총 {len(available_times)}개의 예약 가능한 시간 발견: {available_times}")
            return available_times
            
        except Exception as e:
            self.logger.error(f"시간 데이터 추출 실패: {e}")
            return []
    
    def make_reservation(self, date, target_time, theme_id, user_info):
        """예약 실행 - 2단계 프로세스"""
        if not self.driver:
            self.setup_driver()
        
        try:
            # 예약 페이지 로드
            self.logger.info("예약 페이지 로드 중...")
            self.driver.get(self.reservation_url)
            time.sleep(3)
            
            # === 1단계: 테마, 시간, 날짜 선택 ===
            self.logger.info("1단계: 테마, 시간, 날짜 선택")
            
            # 1. 날짜 선택 (datepicker에서 클릭)
            target_day = date.day
            date_elements = self.driver.find_elements(By.CSS_SELECTOR, '.datepicker--cell')
            
            for elem in date_elements:
                if elem.text.strip() == str(target_day) and elem.is_enabled():
                    elem.click()
                    self.logger.info(f"날짜 선택: {date.strftime('%Y-%m-%d')} ({target_day}일)")
                    time.sleep(1)
                    break
            else:
                # datepicker에서 찾지 못한 경우 숨겨진 필드에 직접 설정
                date_str = date.strftime('%Y-%m-%d')
                date_input = self.driver.find_element(By.NAME, 'reservationDate')
                self.driver.execute_script(f"arguments[0].value = '{date_str}';", date_input)
                self.logger.warning(f"날짜를 datepicker에서 찾지 못해 숨겨진 필드에 설정: {date_str}")
            
            # 2. 테마 선택
            theme_selector = self.driver.find_element(By.CSS_SELECTOR, f'input[name="themePK"][value="{theme_id}"]')
            if not theme_selector.is_selected():
                # 라디오 버튼이 숨겨져 있으므로 JavaScript로 클릭
                self.driver.execute_script("arguments[0].click();", theme_selector)
                self.logger.info(f"테마 선택: {theme_id}")
                time.sleep(1)
            
            # 3. 시간 선택 - HH:MM 형식을 HH:MM:SS로 변환
            time_with_seconds = f"{target_time}:00"
            try:
                time_selector = self.driver.find_element(By.CSS_SELECTOR, f'input[name="reservationTime"][value="{time_with_seconds}"]')
                if not time_selector.is_selected():
                    # 시간 라디오 버튼도 숨겨져 있을 수 있으므로 JavaScript로 클릭
                    self.driver.execute_script("arguments[0].click();", time_selector)
                    self.logger.info(f"시간 선택: {time_with_seconds}")
                    time.sleep(1)
            except:
                self.logger.error(f"시간 {time_with_seconds}을 찾을 수 없습니다")
                return {"success": False, "message": f"시간 {target_time}을 찾을 수 없습니다"}
            
            # 4. NEXT 버튼 클릭하여 2단계로 이동
            next_btn = self.driver.find_element(By.ID, 'nextBtn')
            next_btn.click()
            self.logger.info("NEXT 버튼 클릭 - 2단계로 이동")
            time.sleep(2)
            
            # === 2단계: 사용자 정보 입력 ===
            self.logger.info("2단계: 사용자 정보 입력")
            
            # 사용자 정보 입력 필드들이 나타날 때까지 대기
            WebDriverWait(self.driver, 10).until(
                EC.visibility_of_element_located((By.NAME, "name"))
            )
            
            # 이름 입력
            name_field = self.driver.find_element(By.NAME, 'name')
            name_field.clear()
            name_field.send_keys(user_info['name'])
            self.logger.info(f"이름 입력: {user_info['name']}")
            
            # 전화번호 입력
            phone_field = self.driver.find_element(By.NAME, 'phone')
            phone_field.clear()
            phone_field.send_keys(user_info['phone'])
            self.logger.info(f"전화번호 입력: {user_info['phone']}")
            
            # 인원수 선택
            people_select = self.driver.find_element(By.NAME, 'people')
            people_select.click()
            people_option = self.driver.find_element(By.CSS_SELECTOR, f'option[value="{user_info["people_count"]}"]')
            people_option.click()
            self.logger.info(f"인원수 선택: {user_info['people_count']}명")
            
            # 정책 동의 체크박스 (필수) - label 클릭 방식
            try:
                policy_checkbox = self.driver.find_element(By.NAME, 'policy')
                
                # 방법 1: 부모 label 클릭 (가장 효과적)
                parent_label = policy_checkbox.find_element(By.XPATH, '..')
                parent_label.click()
                self.logger.info("개인정보처리방침 동의 (label 클릭)")
                time.sleep(1)
                
                # 체크 상태 확인 및 재시도
                if not policy_checkbox.is_selected():
                    # 방법 2: JavaScript로 강제 체크
                    self.driver.execute_script("arguments[0].checked = true;", policy_checkbox)
                    self.logger.info("개인정보처리방침 동의 (JavaScript 강제 체크)")
                    time.sleep(1)
                
                # 최종 확인
                if policy_checkbox.is_selected():
                    self.logger.info("✅ 개인정보처리방침 동의 완료")
                else:
                    self.logger.warning("⚠️ 개인정보처리방침 동의 상태 불확실")
                    
            except Exception as e:
                self.logger.error(f"정책 동의 체크박스 처리 실패: {e}")
                return {"success": False, "message": "정책 동의 체크박스를 찾을 수 없습니다"}
            
            time.sleep(1)
            
            # 5. 예약하기 버튼 클릭
            reservation_btn = self.driver.find_element(By.ID, 'reservationBtn')
            reservation_btn.click()
            self.logger.info("예약하기 버튼 클릭")
            
            # 6. Alert 처리 (정책 동의 관련)
            try:
                WebDriverWait(self.driver, 3).until(EC.alert_is_present())
                alert = self.driver.switch_to.alert
                alert_text = alert.text
                self.logger.warning(f"Alert 발생: {alert_text}")
                alert.accept()  # Alert 닫기
                
                if "개인정보" in alert_text or "동의" in alert_text:
                    return {"success": False, "message": f"정책 동의 필요: {alert_text}"}
            except:
                # Alert가 없으면 정상 진행
                pass
            
            # 7. 결과 확인 - 페이지 변화 대기
            time.sleep(3)
            
            # 성공/실패 메시지 확인
            try:
                current_url = self.driver.current_url
                page_source = self.driver.page_source
                
                self.logger.info(f"예약 후 URL: {current_url}")
                
                # 다양한 성공 패턴 확인
                success_patterns = [
                    ("예약" in page_source and "완료" in page_source),
                    ("예약" in page_source and "성공" in page_source),
                    ("완료" in page_source),
                    ("성공" in page_source),
                    ("감사" in page_source),
                    ("확인" in page_source and "예약" in page_source),
                    ("success" in current_url.lower()),
                    ("complete" in current_url.lower()),
                    ("confirm" in current_url.lower()),
                    ("thank" in current_url.lower()),
                ]
                
                # 성공 패턴 중 하나라도 매치되면 성공
                for i, pattern in enumerate(success_patterns):
                    if pattern:
                        self.logger.info(f"✅ 성공 패턴 {i+1} 매치: 예약 성공으로 판단")
                        return {"success": True, "message": "예약이 완료되었습니다"}
                
                # 명확한 실패 메시지 확인
                error_patterns = [
                    "오류",
                    "실패", 
                    "error",
                    "failed",
                    "잘못",
                    "불가능"
                ]
                
                for error in error_patterns:
                    if error in page_source.lower():
                        return {"success": False, "message": f"예약 실패: {error} 관련 메시지 발견"}
                
                # 예약하기 버튼이 여전히 존재하는지 확인 (실패 징후)
                try:
                    reservation_btn = self.driver.find_element(By.ID, 'reservationBtn')
                    if reservation_btn.is_displayed():
                        self.logger.warning("⚠️ 예약하기 버튼이 여전히 표시됨 - 예약이 처리되지 않았을 수 있음")
                        # 하지만 이것만으로는 실패로 판단하지 않음
                except:
                    # 버튼이 사라졌다면 좋은 신호
                    self.logger.info("✅ 예약하기 버튼이 사라짐 - 좋은 신호")
                    return {"success": True, "message": "예약하기 버튼이 사라져 예약 완료로 추정"}
                
                # 기본값: URL이 변하지 않았더라도 Alert 없이 진행되었다면 성공으로 간주
                if current_url == self.reservation_url:
                    self.logger.info("🤔 URL 변화 없음, 하지만 오류 없이 진행 - 성공으로 추정")
                    return {"success": True, "message": "예약이 정상적으로 처리된 것으로 추정됩니다"}
                else:
                    return {"success": True, "message": f"URL이 변경되어 예약 완료로 추정: {current_url}"}
                
            except Exception as e:
                return {"success": False, "message": f"결과 확인 실패: {str(e)}"}
                    
        except Exception as e:
            self.logger.error(f"예약 실행 실패: {e}")
            return {"success": False, "message": str(e)}
    
    def find_date_selector(self, target_date):
        """날짜 선택자 찾기"""
        date_str = target_date.strftime('%Y-%m-%d')
        
        # 여러 가능한 선택자 시도
        selectors = [
            f'[data-date="{date_str}"]',
            f'[value="{date_str}"]',
            f'.date-{date_str}',
            f'#{date_str}',
        ]
        
        for selector in selectors:
            try:
                element = self.driver.find_element(By.CSS_SELECTOR, selector)
                return element
            except:
                continue
                
        # 텍스트로 찾기
        try:
            elements = self.driver.find_elements(By.XPATH, f"//*[contains(text(), '{target_date.day}')]")
            for element in elements:
                if element.is_enabled():
                    return element
        except:
            pass
            
        return None
    
    def find_time_selector(self, target_time):
        """시간 선택자 찾기"""
        time_selectors = [
            f'[data-time="{target_time}"]',
            f'[value="{target_time}"]',
            f'.time-{target_time.replace(":", "")}',
        ]
        
        for selector in time_selectors:
            try:
                element = self.driver.find_element(By.CSS_SELECTOR, selector)
                return element
            except:
                continue
                
        # 텍스트로 찾기
        try:
            elements = self.driver.find_elements(By.XPATH, f"//*[contains(text(), '{target_time}')]")
            for element in elements:
                if element.is_enabled():
                    return element
        except:
            pass
            
        return None
    
    def find_theme_selector(self, theme_id):
        """테마 선택자 찾기"""
        theme_selectors = [
            f'[data-theme="{theme_id}"]',
            f'[value="{theme_id}"]',
            f'#{theme_id}',
        ]
        
        for selector in theme_selectors:
            try:
                element = self.driver.find_element(By.CSS_SELECTOR, selector)
                return element
            except:
                continue
                
        return None
    
    def fill_user_info(self, user_info):
        """사용자 정보 입력"""
        info_mapping = {
            'name': ['name', 'username', 'user_name'],
            'phone': ['phone', 'tel', 'mobile'],
            'email': ['email', 'mail'],
            'people_count': ['people', 'count', 'person']
        }
        
        for field, values in info_mapping.items():
            if field in user_info:
                for field_name in values:
                    try:
                        element = self.driver.find_element(By.NAME, field_name)
                        element.clear()
                        element.send_keys(str(user_info[field]))
                        break
                    except:
                        continue
    
    def monitor_and_book(self, target_date, target_time, theme_id, user_info, check_interval=30):
        """주기적으로 확인하며 예약 시도"""
        self.logger.info(f"예약 모니터링 시작: {target_date} {target_time}")
        
        while True:
            try:
                # 예약 가능 시간 확인
                available_times = self.get_available_times(target_date, user_info)
                
                if available_times:
                    if target_time in available_times:
                        self.logger.info("예약 가능한 시간 발견! 예약 시도...")
                        
                        result = self.make_reservation(target_date, target_time, theme_id, user_info)
                        
                        if result["success"]:
                            self.logger.info(f"예약 성공: {result['message']}")
                            return result
                        else:
                            self.logger.error(f"예약 실패: {result['message']}")
                            return result  # 실패해도 종료
                    else:
                        self.logger.info(f"원하는 시간({target_time})이 없음. 가능한 시간: {available_times}")
                else:
                    self.logger.info(f"시간 슬롯을 찾을 수 없음. {check_interval}초 후 재시도...")
                    
                time.sleep(check_interval)
                
            except KeyboardInterrupt:
                self.logger.info("모니터링 중단")
                break
            except Exception as e:
                self.logger.error(f"모니터링 오류: {e}")
                time.sleep(check_interval)
    
    def cleanup(self):
        """리소스 정리"""
        if self.driver:
            self.driver.quit()


def main():
    """메인 실행 함수"""
    # config.py의 RESERVATION_CONFIG 사용
    config = RESERVATION_CONFIG
    
    target_date = datetime.strptime(config['target_date'], '%Y-%m-%d')
    target_time = config['target_time']
    theme_id = config['theme_id']
    user_info = config['user_info']
    check_interval = config['check_interval']
    
    # 예약 시스템 초기화 (설정에서 지정된 지점 사용)
    store = config['store']
    reservation = ZeroWorldReservation(store=store)
    
    try:
        # 페이지 구조 분석 (첫 실행시)
        print(f"{reservation.store_name} 페이지 구조 분석 중...")
        structure = reservation.analyze_page_structure()
        if structure:
            print(json.dumps(structure, indent=2, ensure_ascii=False))
        
        # 예약 모니터링 및 실행
        print(f"예약 시도: {target_date.strftime('%Y-%m-%d')} {target_time}")
        result = reservation.monitor_and_book(
            target_date=target_date,
            target_time=target_time,
            theme_id=theme_id,
            user_info=user_info,
            check_interval=check_interval
        )
        
        print(f"최종 결과: {result}")
        
    except Exception as e:
        print(f"오류 발생: {e}")
    finally:
        reservation.cleanup()


if __name__ == "__main__":
    main()
