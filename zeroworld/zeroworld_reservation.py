#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import requests
import time
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
        self.reservation_url = f"{self.base_url}/reservation"
        self.store_name = self.store_config['name']
        
        self.session = requests.Session()
        self.driver = None
        self.csrf_token = None
        
        # 로깅 설정
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)
        self.logger.info(f"예약 시스템 초기화: {self.store_name}")
        
        # 날짜별 동적 테마 매핑 저장소 {date_str: {theme_name: theme_id}}
        self.date_theme_mappings = {}
        
        # requests 로깅 비활성화
        import urllib3
        urllib3.disable_warnings()
        logging.getLogger("requests").setLevel(logging.WARNING)
        logging.getLogger("urllib3").setLevel(logging.WARNING)
        
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
        """CSRF 토큰 획득"""
        if self.csrf_token and not force_refresh:
            return self.csrf_token
            
        if not self.driver:
            self.setup_driver(headless=False)
        
        try:
            self.driver.get(self.reservation_url)
            time.sleep(2)
            
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
                for cookie in selenium_cookies:
                    self.session.cookies.set(cookie['name'], cookie['value'])
        except Exception as e:
            self.logger.error(f"쿠키 동기화 실패: {e}")
        
    def get_available_times_for_theme(self, target_date, theme_id, user_info=None, theme_name=None):
        """특정 테마의 예약 가능한 시간 조회"""
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
            
            response = self.session.post(api_url, headers=headers, data=data)
            
            if response.status_code == 200:
                try:
                    result = response.json()
                    
                    # 응답에서 특정 테마의 예약 가능한 시간 추출
                    theme_mapping = self.extract_theme_info(result)
                    
                    # 날짜별 테마 매핑 업데이트
                    if theme_mapping:
                        date_str = target_date.strftime('%Y-%m-%d')
                        self.date_theme_mappings[date_str] = theme_mapping
                    
                    available_times = self.extract_available_times(result, target_theme_id=theme_id, theme_name=theme_name, target_date=target_date)
                    
                    return available_times
                    
                except ValueError as e:
                    self.logger.error(f"JSON 파싱 실패: {e}")
                    return []
            else:
                self.logger.error(f"API 요청 실패: {response.status_code}")
                return []
                
        except Exception as e:
            self.logger.error(f"예약 가능 시간 조회 실패: {e}")
            return []
    
    def extract_available_times(self, api_response, target_theme_id=None, theme_name=None, target_date=None):
        """API 응답에서 예약 가능한 시간 추출 (특정 테마 필터링 지원)"""
        available_times = []
        
        try:
            if isinstance(api_response, dict) and 'times' in api_response:
                times_data = api_response['times']
                
                for theme_id, time_slots in times_data.items():
                    # 특정 테마 ID가 지정된 경우 해당 테마만 필터링
                    if target_theme_id is not None and str(theme_id) != str(target_theme_id):
                        continue
                    
                    if isinstance(time_slots, list):
                        for slot in time_slots:
                            if isinstance(slot, dict) and 'time' in slot and 'reservation' in slot:
                                if not slot['reservation']:
                                    time_str = slot['time']
                                    # HH:MM:SS 형식을 HH:MM으로 변환
                                    if time_str.count(':') == 2:
                                        time_str = time_str.rsplit(':', 1)[0]
                                    available_times.append(time_str)
            
            # 로깅 메시지 개선
            if target_theme_id is not None:
                if theme_name is None and target_date is not None:
                    theme_name = self.get_theme_name_by_id(target_theme_id, target_date)
                if theme_name:
                    self.logger.info(f"테마 '{theme_name}'에서 {len(available_times)}개의 예약 가능한 시간 발견: {available_times}")
            
            return available_times
            
        except Exception as e:
            self.logger.error(f"시간 데이터 추출 실패: {e}")
            return []
    
    def extract_theme_info(self, api_response):
        """API 응답에서 테마 정보 추출"""
        theme_mapping = {}
        
        try:
            if isinstance(api_response, dict) and 'data' in api_response:
                theme_data_list = api_response['data']
                if isinstance(theme_data_list, list):
                    for theme_data in theme_data_list:
                        if isinstance(theme_data, dict) and 'PK' in theme_data and 'title' in theme_data:
                            theme_id = str(theme_data['PK'])
                            theme_title = theme_data['title']
                            
                            # "[홍대] NOX" -> "NOX" 형태로 정리
                            clean_title = theme_title
                            if '] ' in theme_title:
                                clean_title = theme_title.split('] ', 1)[1]
                            
                            theme_mapping[clean_title] = theme_id
                
                return theme_mapping
                
        except Exception as e:
            self.logger.error(f"테마 정보 추출 실패: {e}")
            
        return theme_mapping
    
    def make_reservation(self, date, target_time, theme_id, user_info):
        """예약 실행"""
        if not self.driver:
            self.setup_driver()
        
        try:
            self.logger.info("예약 페이지 로드 중...")
            self.driver.get(self.reservation_url)
            time.sleep(3)
            
            # 1단계: 테마, 시간, 날짜 선택
            self.logger.info("테마, 시간, 날짜 선택 중...")
            
            # 날짜 선택
            target_day = date.day
            date_elements = self.driver.find_elements(By.CSS_SELECTOR, '.datepicker--cell')
            
            for elem in date_elements:
                if elem.text.strip() == str(target_day) and elem.is_enabled():
                    elem.click()
                    self.logger.info(f"날짜 선택: {date.strftime('%Y-%m-%d')}")
                    time.sleep(1)
                    break
            else:
                date_str = date.strftime('%Y-%m-%d')
                date_input = self.driver.find_element(By.NAME, 'reservationDate')
                self.driver.execute_script(f"arguments[0].value = '{date_str}';", date_input)
            
            # 테마 선택
            theme_selector = self.driver.find_element(By.CSS_SELECTOR, f'input[name="themePK"][value="{theme_id}"]')
            if not theme_selector.is_selected():
                self.driver.execute_script("arguments[0].click();", theme_selector)
                self.logger.info(f"테마 선택: {theme_id}")
                time.sleep(1)
            
            # 시간 선택
            time_with_seconds = f"{target_time}:00"
            try:
                time_selector = self.driver.find_element(By.CSS_SELECTOR, f'input[name="reservationTime"][value="{time_with_seconds}"]')
                if not time_selector.is_selected():
                    self.driver.execute_script("arguments[0].click();", time_selector)
                    self.logger.info(f"시간 선택: {time_with_seconds}")
                    time.sleep(1)
            except:
                self.logger.error(f"시간 {time_with_seconds}을 찾을 수 없습니다")
                return {"success": False, "message": f"시간 {target_time}을 찾을 수 없습니다"}
            
            # NEXT 버튼 클릭
            next_btn = self.driver.find_element(By.ID, 'nextBtn')
            next_btn.click()
            self.logger.info("다음 단계로 이동")
            time.sleep(2)
            
            # 2단계: 사용자 정보 입력
            self.logger.info("사용자 정보 입력 중...")
            
            WebDriverWait(self.driver, 10).until(
                EC.visibility_of_element_located((By.NAME, "name"))
            )
            
            # 이름 입력
            name_field = self.driver.find_element(By.NAME, 'name')
            name_field.clear()
            name_field.send_keys(user_info['name'])
            
            # 전화번호 입력
            phone_field = self.driver.find_element(By.NAME, 'phone')
            phone_field.clear()
            phone_field.send_keys(user_info['phone'])
            
            # 인원수 선택
            people_select = self.driver.find_element(By.NAME, 'people')
            people_select.click()
            people_option = self.driver.find_element(By.CSS_SELECTOR, f'option[value="{user_info["people_count"]}"]')
            people_option.click()
            
            # 정책 동의 체크박스
            try:
                policy_checkbox = self.driver.find_element(By.NAME, 'policy')
                parent_label = policy_checkbox.find_element(By.XPATH, '..')
                parent_label.click()
                time.sleep(1)
                
                if not policy_checkbox.is_selected():
                    self.driver.execute_script("arguments[0].checked = true;", policy_checkbox)
                    time.sleep(1)
                
            except Exception as e:
                self.logger.error(f"정책 동의 체크박스 처리 실패: {e}")
                return {"success": False, "message": "정책 동의 체크박스를 찾을 수 없습니다"}
            
            time.sleep(1)
            
            # 예약하기 버튼 클릭
            reservation_btn = self.driver.find_element(By.ID, 'reservationBtn')
            reservation_btn.click()
            self.logger.info("예약 요청 전송")
            
            # Alert 처리
            try:
                WebDriverWait(self.driver, 3).until(EC.alert_is_present())
                alert = self.driver.switch_to.alert
                alert_text = alert.text
                self.logger.warning(f"Alert 발생: {alert_text}")
                alert.accept()
                
                if "개인정보" in alert_text or "동의" in alert_text:
                    return {"success": False, "message": f"정책 동의 필요: {alert_text}"}
            except:
                pass
            
            # 결과 확인
            time.sleep(3)
            
            try:
                current_url = self.driver.current_url
                page_source = self.driver.page_source
                
                # 성공 패턴 확인
                success_patterns = [
                    ("예약" in page_source and "완료" in page_source),
                    ("예약" in page_source and "성공" in page_source),
                    ("완료" in page_source),
                    ("성공" in page_source),
                    ("감사" in page_source),
                    ("success" in current_url.lower()),
                    ("complete" in current_url.lower()),
                ]
                
                for pattern in success_patterns:
                    if pattern:
                        return {"success": True, "message": "예약이 완료되었습니다"}
                
                # 예약하기 버튼이 사라졌는지 확인
                try:
                    reservation_btn = self.driver.find_element(By.ID, 'reservationBtn')
                    if not reservation_btn.is_displayed():
                        return {"success": True, "message": "예약이 완료되었습니다"}
                except:
                    return {"success": True, "message": "예약이 완료되었습니다"}
                
                return {"success": True, "message": "예약이 정상적으로 처리된 것으로 추정됩니다"}
                
            except Exception as e:
                return {"success": False, "message": f"결과 확인 실패: {str(e)}"}
                    
        except Exception as e:
            self.logger.error(f"예약 실행 실패: {e}")
            return {"success": False, "message": str(e)}
    
    def check_and_book(self, target_date, time_range, theme_name, user_info):
        """특정 날짜에 예약 가능한 시간이 있는지 확인하고 예약 시도"""
        self.logger.info(f"예약 확인: {target_date.strftime('%Y-%m-%d')} {time_range['start']}-{time_range['end']} (테마: {theme_name})")
        
        try:
            # 먼저 해당 날짜의 모든 테마 정보를 가져와서 매핑 업데이트
            self.get_available_times_for_theme(target_date, None, user_info, theme_name)
            
            # 테마명으로 테마 ID 찾기
            try:
                theme_id = self.get_theme_id_by_name(theme_name, target_date)
            except ValueError as e:
                return {"success": False, "message": str(e)}
            
            # 특정 테마의 예약 가능 시간 확인
            available_times = self.get_available_times_for_theme(target_date, theme_id, user_info, theme_name)
            
            if available_times:
                # 시간 구간 내에서 예약 가능한 시간 찾기
                available_in_range = self.find_available_time_in_range(available_times, time_range)
                
                if available_in_range:
                    target_time = available_in_range[0]
                    self.logger.info(f"예약 가능한 시간 발견! 예약 시도: {target_time}")
                    
                    result = self.make_reservation(target_date, target_time, theme_id, user_info)
                    
                    if result["success"]:
                        self.logger.info(f"예약 성공: {result['message']} (시간: {target_time})")
                        return {"success": True, "message": result['message'], "time": target_time}
                    else:
                        self.logger.error(f"예약 실패: {result['message']}")
                        return {"success": False, "message": result['message'], "time": target_time}
                else:
                    self.logger.info(f"시간 구간 {time_range['start']}-{time_range['end']} 내 예약 가능한 시간 없음")
                    return {"success": False, "message": f"시간 구간 {time_range['start']}-{time_range['end']} 내 예약 가능한 시간 없음"}
            else:
                return {"success": False, "message": f"테마 '{theme_name}'에서 예약 가능한 시간 없음"}
            
        except Exception as e:
            self.logger.error(f"예약 확인 오류: {e}")
            return {"success": False, "message": f"예약 확인 오류: {str(e)}"}
    
    def get_theme_id_by_name(self, theme_name, target_date):
        """특정 날짜의 테마명으로 테마 ID 찾기"""
        date_str = target_date.strftime('%Y-%m-%d')
        
        if date_str in self.date_theme_mappings:
            theme_mapping = self.date_theme_mappings[date_str]
            if theme_name in theme_mapping:
                theme_id = theme_mapping[theme_name]
                self.logger.info(f"테마명 변환: '{theme_name}' -> ID '{theme_id}' ({date_str})")
                return theme_id
            
            available_themes = list(theme_mapping.keys())
            raise ValueError(f"테마를 찾을 수 없습니다: '{theme_name}'. {date_str}에 사용 가능한 테마: {available_themes}")
        else:
            raise ValueError(f"{date_str}에 대한 테마 정보가 로드되지 않았습니다.")
    
    def get_theme_name_by_id(self, theme_id, target_date):
        """특정 날짜의 테마 ID로 테마명 찾기"""
        date_str = target_date.strftime('%Y-%m-%d')
        
        if date_str in self.date_theme_mappings:
            theme_mapping = self.date_theme_mappings[date_str]
            for theme_name, tid in theme_mapping.items():
                if str(tid) == str(theme_id):
                    return theme_name
        
        # 모든 날짜에서 찾기 (fallback)
        for date_mapping in self.date_theme_mappings.values():
            for theme_name, tid in date_mapping.items():
                if str(tid) == str(theme_id):
                    return theme_name
        
        return f"테마ID:{theme_id}"  # 테마명을 찾지 못한 경우 ID 표시
    
    def list_available_themes(self):
        """모든 날짜의 사용 가능한 테마 목록 반환"""
        all_themes = set()
        for date_mapping in self.date_theme_mappings.values():
            all_themes.update(date_mapping.keys())
        return list(all_themes)
    
    def find_available_time_in_range(self, available_times, time_range):
        """시간 구간 내에서 예약 가능한 시간 찾기"""
        start_time = datetime.strptime(time_range['start'], '%H:%M').time()
        end_time = datetime.strptime(time_range['end'], '%H:%M').time()
        
        available_in_range = []
        
        for time_str in available_times:
            try:
                if time_str.count(':') == 2:
                    time_str = time_str.rsplit(':', 1)[0]
                
                time_obj = datetime.strptime(time_str, '%H:%M').time()
                
                if start_time <= time_obj <= end_time:
                    available_in_range.append(time_str)
                    
            except ValueError:
                continue
        
        available_in_range.sort()
        self.logger.info(f"시간 구간 {time_range['start']}-{time_range['end']} 내 예약 가능한 시간: {available_in_range}")
        return available_in_range
    
    def cleanup(self):
        """리소스 정리"""
        if self.driver:
            self.driver.quit()


def main():
    """메인 실행 함수"""
    config = RESERVATION_CONFIG
    
    # 여러 날짜 지원
    target_dates = []
    if 'target_dates' in config:
        for date_str in config['target_dates']:
            target_dates.append(datetime.strptime(date_str, '%Y-%m-%d'))
    elif 'target_date' in config:
        target_dates.append(datetime.strptime(config['target_date'], '%Y-%m-%d'))
    else:
        raise ValueError("target_dates 또는 target_date 설정이 필요합니다")
    
    if 'time_range' not in config:
        raise ValueError("time_range 설정이 필요합니다")
    
    time_range = config['time_range']
    if 'start' not in time_range or 'end' not in time_range:
        raise ValueError("time_range에 start와 end 시간을 모두 지정해야 합니다")
    
    if 'theme' not in config:
        raise ValueError("theme 설정이 필요합니다")
    
    theme_name = config['theme']
    user_info = config['user_info']
    check_interval = config['check_interval']
    
    # 예약 시스템 초기화
    store = config['store']
    reservation = ZeroWorldReservation(store=store)
    
    try:
        # 테마 정보 로드 (첫 번째 날짜로 초기화)
        print(f"테마 정보 로드 중...")
        attempts = 0
        max_attempts = 3
        while attempts < max_attempts and not reservation.date_theme_mappings:
            attempts += 1
            print(f"테마 정보 로드 시도 {attempts}/{max_attempts}...")
            reservation.get_available_times_for_theme(target_dates[0], None, user_info, theme_name)
            if reservation.date_theme_mappings:
                break
            time.sleep(2)  # 잠깐 대기 후 재시도
        
        if not reservation.date_theme_mappings:
            print(f"⚠️  테마 정보 로드 실패. API 응답을 확인해주세요.")
            return
        
        print(f"대상 테마: '{theme_name}'")
        
        # 사용 가능한 테마 목록 표시
        available_themes = reservation.list_available_themes()
        if available_themes:
            print(f"현재 사용 가능한 테마: {available_themes}")
        
        # 예약이 성공할 때까지 주기적으로 모든 날짜 확인
        print(f"📅 {len(target_dates)}개 날짜에 대해 {check_interval}초마다 확인합니다...")
        
        while True:
            try:
                success = False
                for i, target_date in enumerate(target_dates, 1):
                    print(f"[{i}/{len(target_dates)}] 📅 예약 확인: {target_date.strftime('%Y-%m-%d')} {time_range['start']}-{time_range['end']} (테마: {theme_name})")
                    
                    result = reservation.check_and_book(
                        target_date=target_date,
                        time_range=time_range,
                        theme_name=theme_name,
                        user_info=user_info
                    )
                    
                    if result["success"]:
                        booked_time = result.get("time", "알 수 없음")
                        print(f"✅ 예약 성공: {target_date.strftime('%Y-%m-%d')} {booked_time} - {result['message']}")
                        success = True
                        break
                    else:
                        failed_time = result.get("time", "")
                        time_info = f" {failed_time}" if failed_time else ""
                        print(f"❌ 예약 실패: {target_date.strftime('%Y-%m-%d')}{time_info} - {result['message']}")
                
                if success:
                    print("예약이 완료되었습니다!")
                    break
                else:
                    print(f"모든 날짜에서 예약 불가. {check_interval}초 후 다시 시도...")
                    time.sleep(check_interval)
                    
            except KeyboardInterrupt:
                print("사용자에 의해 중단되었습니다.")
                break
        
    except Exception as e:
        print(f"오류 발생: {e}")
    finally:
        reservation.cleanup()


if __name__ == "__main__":
    main()