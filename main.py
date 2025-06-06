import gspread
from google.oauth2.service_account import Credentials
from bs4 import BeautifulSoup
import requests
import time
import logging
import re

# Настройки скрипта
WAYBACK_REQUEST_DELAY = 2  # Задержка между запросами к Wayback Machine (в секундах)
WAYBACK_RETRY_DELAY = 10    # Задержка между повторными попытками при ошибке Wayback Machine (в секундах)
SHEETS_REQUEST_DELAY = 1   # Задержка между запросами к Google Sheets API (в секундах)
GOOGLE_API_RETRY_DELAY = 90  # Задержка между попытками при ошибке Google API (в секундах)
REQUEST_TIMEOUT = 90  # Таймаут для HTTP-запросов
WAYBACK_LIMIT = 3  # Максимальное количество последних снимков из Wayback Machine
MAX_RETRIES = 5  # Максимальное количество попыток при ошибке запроса
GOOGLE_API_MAX_RETRIES = 3  # Максимальное количество попыток при ошибке Google API
BATCH_SIZE = 10  # Размер пакета для записи в Google Sheets (можно менять)
WAYBACK_CDX_URL_TEMPLATE = "https://web.archive.org/cdx/search/cdx?url={domain}&output=json&limit={limit}&fl=timestamp&filter=statuscode:200&sort=desc"
WAYBACK_SNAPSHOT_URL_TEMPLATE = "https://web.archive.org/web/{timestamp}/http://{domain}/"
SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/11PRL7WHEWC9vzYEPglbXYq_UX-xA0GXokfslBYKerZ2M1/edit?gid=0#gid=0"
LOG_FILE = "wayback_script.log"  # Путь к лог-файлу
LOG_LEVEL = "INFO"  # Уровень логирования - DEBUG INFO WARNING ERROR CRITICAL

# Настройка логирования с явным указанием кодировки UTF-8
logging.basicConfig(
    filename=LOG_FILE,
    level=LOG_LEVEL,
    format='%(asctime)s - %(levelname)s - %(message)s',
    encoding='utf-8'
)
logging.info("Запуск скрипта...")

# Настройка авторизации для Google Sheets
scope = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
creds = Credentials.from_service_account_file('credentials.json', scopes=scope)
client = gspread.authorize(creds)

# Функция для экранирования названия листа
def escape_worksheet_title(title):
    # Удаляем или заменяем недопустимые символы
    return re.sub(r'[\[\]:\*\?/\\]', '_', title.strip())

# Открытие таблицы с повторными попытками
spreadsheet = None
for attempt in range(GOOGLE_API_MAX_RETRIES):
    try:
        spreadsheet = client.open_by_url(SPREADSHEET_URL)
        print(f"Таблица успешно открыта: {spreadsheet.title}")
        logging.info(f"Таблица успешно открыта: {spreadsheet.title}")
        break
    except gspread.exceptions.APIError as e:
        if attempt == GOOGLE_API_MAX_RETRIES - 1:
            print(f"Ошибка при открытии таблицы после {GOOGLE_API_MAX_RETRIES} попыток: {e}")
            logging.error(f"Ошибка при открытии таблицы после {GOOGLE_API_MAX_RETRIES} попыток: {e}")
            exit(1)
        print(f"Попытка {attempt + 1} не удалась, жду {GOOGLE_API_RETRY_DELAY} секунд...")
        logging.warning(f"Попытка {attempt + 1} не удалась: {str(e)}")
        time.sleep(GOOGLE_API_RETRY_DELAY)

# Функция для получения первого пустого столбца
def get_first_empty_column(row):
    return len(row) + 1 if row else 1

# Обработка каждого листа
for worksheet in spreadsheet.worksheets():
    escaped_title = escape_worksheet_title(worksheet.title)
    print(f"Обрабатываю лист: {escaped_title}")
    logging.info(f"Обрабатываю лист: {escaped_title}")
    rows = None
    for attempt in range(GOOGLE_API_MAX_RETRIES):
        try:
            rows = worksheet.get_all_values()
            break
        except gspread.exceptions.APIError as e:
            if attempt == GOOGLE_API_MAX_RETRIES - 1:
                print(f"Лист {escaped_title}: ошибка получения данных после {GOOGLE_API_MAX_RETRIES} попыток: {e}")
                logging.error(f"Лист {escaped_title}: ошибка получения данных после {GOOGLE_API_MAX_RETRIES} попыток: {e}")
                rows = []
                break
            print(f"Лист {escaped_title}: попытка {attempt + 1} не удалась, жду {GOOGLE_API_RETRY_DELAY} секунд...")
            logging.warning(f"Лист {escaped_title}: попытка {attempt + 1} не удалась: {str(e)}")
            time.sleep(GOOGLE_API_RETRY_DELAY)

    if len(rows) < 2:
        print(f"Лист {escaped_title}: пустой или содержит только заголовок, пропускаю...")
        logging.info(f"Лист {escaped_title}: пустой или содержит только заголовок, пропускаю...")
        continue

    # Список для накопления обновлений
    updates = []
    processed_domains = 0

    for row_idx, row in enumerate(rows[1:], start=2):
        domain = row[0].strip()
        if not domain:
            print(f"Лист {escaped_title}, строка {row_idx}: пустой домен, пропускаю...")
            logging.info(f"Лист {escaped_title}, строка {row_idx}: пустой домен, пропускаю...")
            continue

        print(f"Лист {escaped_title}, строка {row_idx}: обработка домена {domain}")
        logging.info(f"Лист {escaped_title}, строка {row_idx}: обработка домена {domain}")
        try:
            # Запрос к Wayback CDX API с повторными попытками
            cdx_url = WAYBACK_CDX_URL_TEMPLATE.format(domain=domain, limit=WAYBACK_LIMIT)
            data = None
            for attempt in range(MAX_RETRIES):
                try:
                    response = requests.get(cdx_url, timeout=REQUEST_TIMEOUT)
                    response.raise_for_status()
                    data = response.json()
                    break
                except requests.RequestException as e:
                    if attempt == MAX_RETRIES - 1:
                        error_message = f"Ошибка запроса к Wayback Machine (CDX API): {str(e)}"
                        print(f"Лист {escaped_title}, строка {row_idx}: {error_message}")
                        logging.error(f"Лист {escaped_title}, строка {row_idx}: {error_message}")
                        raise
                    print(f"Лист {escaped_title}, строка {row_idx}: попытка {attempt + 1} не удалась, жду {WAYBACK_RETRY_DELAY} секунд...")
                    logging.warning(f"Лист {escaped_title}, строка {row_idx}: попытка {attempt + 1} не удалась: {str(e)}")
                    time.sleep(WAYBACK_RETRY_DELAY)

            # Проверка наличия снимков
            if len(data) <= 1 or not data[1]:
                print(f"Лист {escaped_title}, строка {row_idx}: нет доступных снимков")
                logging.info(f"Лист {escaped_title}, строка {row_idx}: нет доступных снимков")
                title = "нет доступных снимков"
            else:
                timestamp = data[1][0]  # Берем самый старый снимок
                wayback_url = WAYBACK_SNAPSHOT_URL_TEMPLATE.format(timestamp=timestamp, domain=domain)

                # Запрос к снимку с повторными попытками
                response = None
                for attempt in range(MAX_RETRIES):
                    try:
                        response = requests.get(wayback_url, timeout=REQUEST_TIMEOUT)
                        response.raise_for_status()
                        break
                    except requests.RequestException as e:
                        if attempt == MAX_RETRIES - 1:
                            error_message = f"Ошибка запроса к Wayback Machine (снимок): {str(e)}"
                            print(f"Лист {escaped_title}, строка {row_idx}: {error_message}")
                            logging.error(f"Лист {escaped_title}, строка {row_idx}: {error_message}")
                            raise
                        print(f"Лист {escaped_title}, строка {row_idx}: попытка {attempt + 1} не удалась, жду {WAYBACK_RETRY_DELAY} секунд...")
                        logging.warning(f"Лист {escaped_title}, строка {row_idx}: попытка {attempt + 1} не удалась: {str(e)}")
                        time.sleep(WAYBACK_RETRY_DELAY)

                soup = BeautifulSoup(response.text, 'html.parser')
                title_tag = soup.find('title')
                if title_tag:
                    title = title_tag.text.strip()
                    print(f"Лист {escaped_title}, строка {row_idx}: найден title: {title}")
                    logging.info(f"Лист {escaped_title}, строка {row_idx}: найден title: {title}")
                else:
                    error_message = f"Ошибка: не удалось извлечь <title> из снимка {timestamp}"
                    print(f"Лист {escaped_title}, строка {row_idx}: {error_message}")
                    logging.error(f"Лист {escaped_title}, строка {row_idx}: {error_message}")
                    title = error_message

        except requests.RequestException as e:
            error_message = f"Ошибка запроса к Wayback Machine: {str(e)}"
            print(f"Лист {escaped_title}, строка {row_idx}: {error_message}")
            logging.error(f"Лист {escaped_title}, строка {row_idx}: {error_message}")
            title = error_message
        except (ValueError, IndexError) as e:
            error_message = f"Ошибка обработки данных: {str(e)}"
            print(f"Лист {escaped_title}, строка {row_idx}: {error_message}")
            logging.error(f"Лист {escaped_title}, строка {row_idx}: {error_message}")
            title = error_message
        except Exception:
            print(f"Лист {escaped_title}, строка {row_idx}: неизвестная ошибка")
            logging.error(f"Лист {escaped_title}, строка {row_idx}: неизвестная ошибка")
            title = "N/A"

        # Определяем столбец для записи
        col_idx = get_first_empty_column(row)

        # Добавляем обновление в список
        updates.append({
            'range': f"{gspread.utils.rowcol_to_a1(row_idx, col_idx)}",
            'values': [[title]]
        })
        processed_domains += 1

        print(f"Лист {escaped_title}, строка {row_idx}: подготовлен результат: {title}")
        logging.info(f"Лист {escaped_title}, строка {row_idx}: подготовлен результат: {title}")

        # Пакетная запись, если накопилось BATCH_SIZE доменов или это последний домен
        if len(updates) >= BATCH_SIZE or row_idx == len(rows):
            for attempt in range(GOOGLE_API_MAX_RETRIES):
                try:
                    print(f"Лист {escaped_title}: записываю пакет из {len(updates)} доменов...")
                    logging.info(f"Лист {escaped_title}: записываю пакет из {len(updates)} доменов...")
                    worksheet.batch_update(updates)
                    updates = []  # Очищаем список после записи
                    time.sleep(SHEETS_REQUEST_DELAY)  # Задержка после записи пакета
                    break
                except gspread.exceptions.APIError as e:
                    if attempt == GOOGLE_API_MAX_RETRIES - 1:
                        print(f"Лист {escaped_title}: ошибка пакетной записи после {GOOGLE_API_MAX_RETRIES} попыток: {e}")
                        logging.error(f"Лист {escaped_title}: ошибка пакетной записи после {GOOGLE_API_MAX_RETRIES} попыток: {e}")
                        updates = []  # Очищаем список и продолжаем
                        break
                    print(f"Лист {escaped_title}: попытка {attempt + 1} не удалась, жду {GOOGLE_API_RETRY_DELAY} секунд...")
                    logging.warning(f"Лист {escaped_title}: попытка {attempt + 1} не удалась: {str(e)}")
                    time.sleep(GOOGLE_API_RETRY_DELAY)

        # Задержка для Wayback Machine
        time.sleep(WAYBACK_REQUEST_DELAY)

print("Скрипт успешно завершён!")
logging.info("Скрипт успешно завершён!")
