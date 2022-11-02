import logging
import os
import sys
import time
from typing import Dict, List

import requests
import telegram
from dotenv import load_dotenv

import exceptions

load_dotenv()


PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_TIME = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_STATUSES = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

logging.basicConfig(
    level=logging.DEBUG,
    filename='program.log',
    filemode='w',
    format='%(asctime)s - %(levelname)s - %(message)s - %(name)s'
)
logger = logging.getLogger(__name__)
logger.addHandler(logging.StreamHandler())


def send_message(bot, message):
    """Отправляет сообщения пользователю."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logger.info(f"Бот отправил сообщение '{message}'")
    except telegram.TelegramError:
        logger.error(
            f'Бот не отправил сообщение "{message}" из-за ',
            exc_info=True
        )


def get_api_answer(current_timestamp) -> Dict:
    """Делает запрос к API."""
    timestamp = current_timestamp or int(time.time())
    params = {'from_date': timestamp}
    try:
        homework_statuses = requests.get(
            ENDPOINT,
            headers=HEADERS,
            params=params
        )
        if homework_statuses.status_code != 200:
            error_message = (
                f'Сбой запроса к эндпоинту. '
                f'Статус {homework_statuses.status_code}'
            )
            send_message(telegram.Bot(token=TELEGRAM_TOKEN), error_message)
            logger.error(error_message)
            raise exceptions.StatusCodeError(
                Exception,
                homework_statuses.status_code
            )
        return homework_statuses.json()
    except requests.exceptions.RequestException as error:
        error_message = (
            f'Проблемы при работе с API Практикума. {error}'
        )
        logger.error(error_message)
        raise Exception(error_message)


def check_response(response) -> List:
    """Проверяет ответ API на корректность."""
    if not isinstance(response["homeworks"], list):
        error_message = "Неверный тип данных"
        logger.error(error_message)
        raise TypeError(error_message)
    else:
        try:
            response["homeworks"]
            return response["homeworks"]
        except Exception:
            if not response["homeworks"]:
                error_message = "Пришел пустой словарь"
                logger.error(error_message)
                raise Exception(error_message)
            else:
                error_message = "Отсутствуют ожидаемые ключи в ответе API"
                logger.error(error_message)
                raise Exception(error_message)


def parse_status(homework) -> str:
    """Извлекает из информации о  домашней работе."""
    if 'homework_name' not in homework:
        raise KeyError('Отсутствует ключ "homework_name" в ответе API')
    if 'status' not in homework:
        raise KeyError('Отсутствует ключ "status" в ответе API')
    homework_name = homework['homework_name']
    homework_status = homework['status']
    if homework_status not in HOMEWORK_STATUSES:
        raise Exception(f'Неизвестный статус работы: {homework_status}')
    verdict = HOMEWORK_STATUSES[homework_status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens() -> bool:
    """Проверяет наличие обязательных переменных окружения."""
    if PRACTICUM_TOKEN and TELEGRAM_TOKEN and TELEGRAM_CHAT_ID:
        return True
    else:
        error_message = (
            "Отсутствует(ют) обязательная(ые) переменная(ые) окружения: "
        )
        if not PRACTICUM_TOKEN:
            error_message += 'PRACTICUM_TOKEN '
        if not TELEGRAM_TOKEN:
            error_message += 'TELEGRAM_TOKEN '
        if not TELEGRAM_CHAT_ID:
            error_message += 'TELEGRAM_CHAT_ID'
        logger.critical(error_message)
        return False

def main():
    """Основная логика работы бота."""
    if not check_tokens():
        sys.exit("Отсутствуют обязательные переменные окружения.")
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())
    message = ''
    while True:
        try:
            response = get_api_answer(current_timestamp)
            homework = check_response(response)
            new_message = parse_status(homework[0])
            if homework and (message != new_message):
                message = new_message
                send_message(bot, message)
            current_timestamp = response.get("current_date")

        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logger.error(message)
            send_message(telegram.Bot(token=TELEGRAM_TOKEN), message)
        finally:
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    main()
