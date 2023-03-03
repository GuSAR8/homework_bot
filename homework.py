import os
import sys
import telegram
import requests
import time
import logging

from logging import StreamHandler

from dotenv import load_dotenv


load_dotenv()

logger = logging.getLogger(__name__)
handler = StreamHandler(stream=sys.stdout)
formatter = logging.Formatter(
    '%(asctime)s - [%(levelname)s] - %(message)s'
)
handler.setFormatter(formatter)
logger.addHandler(handler)

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}
PAYLOAD = {'from_date': 1675231390}


HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


def check_tokens():
    """Проверяет доступность переменных окружения."""
    if None in (PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID):
        logger.critical('Отсутствуют обязательные переменные окружения')
        return False
    return True


def send_message(bot, message):
    """Отправляет сообщение в Telegram чат."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logger.debug('Сообщение Telegram отправленно')
    except Exception:
        logger.error('Сбой при отправке сообщения в Telegram')


def get_api_answer(timestamp):
    """Делает запрос к API-сервису. Возвращает из JSON в Python."""
    PAYLOAD['from_date'] = timestamp
    try:
        homework_status = requests.get(
            ENDPOINT, headers=HEADERS, params=PAYLOAD
        )
    except requests.exceptions.RequestException:
        logger.error('Недоступность эндпоинта Yandex Practikum')
    else:
        if homework_status.status_code == 200:
            return homework_status.json()
        else:
            message = (f'Ожидаемый код: 200, но вернулся код: '
                       f'{homework_status.status_code}')
            logger.error(message)
            raise requests.ConnectionError(message)


def check_response(response):
    """Проверяет ответ API на соответствие документации."""
    if type(response) is not dict:
        raise TypeError('response is not dict')
    homeworks = response.get('homeworks')
    if homeworks is None:
        raise KeyError('В response нет ключа "homeworks"')
    if type(homeworks) is not list:
        raise TypeError(
            'В ответе API домашки под ключом "homeworks" данные не списком.')
    for k in ('current_date', 'homeworks'):
        if k not in response:
            message = f'Отсутствие ожидаемого ключа {k} в ответе API'
            logger.error(message)
            raise KeyError(message)
    return homeworks


def parse_status(homework):
    """Возвращает подготовленную для отправки в Telegram строку."""
    homework_name = homework.get('homework_name')
    status = homework.get('status')
    verdict = HOMEWORK_VERDICTS.get(status)
    if homework_name is None:
        logger.error('В ответе API домашки нет ключа "homework_name"')
        raise KeyError('Ожидали имя домашней работы, но не получили')
    if status is None:
        logger.error('Домашняя работа вернулась без статуса')
        raise KeyError('status')
    if verdict is None:
        logger.error(f'Неожиданный статус домашней работы '
                     f'"{status}", обнаруженный в ответе API')
        raise KeyError('status')
    print(verdict, '!!!!!!!!!!!!!!!!!!!!!!!!!!!!!')
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        return
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = 1675231390
    current_status = 'reviewing'
    while True:
        try:
            response = get_api_answer(timestamp)
            homework = check_response(response)
            if current_status != homework[0].get('status'):
                answer = parse_status(response.get('homeworks')[0])
                send_message(bot, answer)
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logger.error(message)
        time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
