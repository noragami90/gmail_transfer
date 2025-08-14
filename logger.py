"""
Настройка логирования для проекта переноса Gmail почты
"""
import logging
import colorlog
import os
from datetime import datetime
from config import LOG_LEVEL

def setup_logger(name: str = __name__) -> logging.Logger:
    """
    Настраивает и возвращает логгер с цветным выводом в консоль и записью в файл
    
    Args:
        name: Имя логгера
        
    Returns:
        Настроенный логгер
    """
    
    # Создаем директорию для логов если не существует
    logs_dir = "logs"
    if not os.path.exists(logs_dir):
        os.makedirs(logs_dir)
    
    # Создаем логгер
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, LOG_LEVEL.upper()))
    
    # Избегаем дублирования handlers при повторном вызове
    if logger.handlers:
        return logger
    
    # Форматтер для консоли с цветами
    console_formatter = colorlog.ColoredFormatter(
        '%(log_color)s%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        log_colors={
            'DEBUG': 'cyan',
            'INFO': 'green',
            'WARNING': 'yellow',
            'ERROR': 'red',
            'CRITICAL': 'red,bg_white',
        }
    )
    
    # Форматтер для файла
    file_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Handler для консоли
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    
    # Handler для файла
    log_filename = f"{logs_dir}/gmail_transfer_{datetime.now().strftime('%Y%m%d')}.log"
    file_handler = logging.FileHandler(log_filename, encoding='utf-8')
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)
    
    return logger
