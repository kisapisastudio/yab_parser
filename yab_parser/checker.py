import os
from yab_parser import config


def check_structure() -> list[str]:
    '''
    Check if the structure of the project is correct.
    '''
    config.logger.info('Checking the project structure.')
    report = []

    for path in config.NESSESSARY_PATHS:
        if not os.path.exists(path):
            report.append(f'The path {path} does not exist.')
    if report:
        return report

    if not os.path.exists(config.MEDIA_PATH):
        os.mkdir(config.MEDIA_PATH)

    story_files = os.listdir(config.STORY_PATH)
    for file in story_files:
        if file.endswith('.yarn'):
            break
    else:
        report.append('The Story folder does not contain any .yarn files.')
    return report
