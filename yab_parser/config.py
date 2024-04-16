import os
from dotenv import load_dotenv
from loguru import logger
import sys

dotenv_path = os.path.join(os.path.dirname(__file__), '.env')
logger.remove()
logger.add(sys.stdout, level='INFO', format='{level}|{time}|{message}')
if os.path.exists(dotenv_path):
    IS_DEV = True
    load_dotenv(dotenv_path)
    logger.info('Loaded .env file')
else:
    IS_DEV = False

current_file_path = os.path.abspath(__file__)
current_dir_path = os.path.dirname(current_file_path)
LARK_GRAMMAR_PATH = os.path.join(current_dir_path, 'yarnspinner.lark')
EXAMPLE_MEDIA_DIR = os.path.join(current_dir_path, 'example_media')
EXAMPLE_JPG_PATH = os.path.join(EXAMPLE_MEDIA_DIR, 'example.jpeg')
EXAMPLE_PNG_PATH = os.path.join(EXAMPLE_MEDIA_DIR, 'example.png')
EXAMPLE_OOG_PATH = os.path.join(EXAMPLE_MEDIA_DIR, 'example.ogg')
EXAMPLE_MP4_PATH = os.path.join(EXAMPLE_MEDIA_DIR, 'example.mp4')
EXAMPLE_MOV_PATH = os.path.join(EXAMPLE_MEDIA_DIR, 'example.mov')


STORY_PATH = 'Story'
MEDIA_PATH = 'Media'
TRANSLATION_PATH = 'Translation'
SETTINGS_PATH = os.path.join('Settings', 'settings.yaml')
NESSESSARY_PATHS = [STORY_PATH, SETTINGS_PATH]
BUILD_PATH = 'build.yab'

SUPPORTED_LANGUAGES = ['ru', 'en']
