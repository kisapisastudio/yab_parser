from yab_parser import builder, checker, config
import os
import zipfile


def get_script() -> tuple[builder.YabScriptBuilder | None, list[str]]:
    structure_errors = checker.check_structure()
    if structure_errors:
        return None, structure_errors

    paths = []
    errors = []
    for file in os.listdir(config.STORY_PATH):
        if file.endswith('.yarn'):
            paths.append(os.path.join(config.STORY_PATH, file))
    if not paths:
        errors.append('The Story folder does not contain any .yarn files.')
    if not os.path.exists(config.SETTINGS_PATH):
        errors.append(f'The path {config.SETTINGS_PATH} does not exist.')
    if errors:
        return None, errors

    script = builder.YabScriptBuilder(paths, config.SETTINGS_PATH)
    errors += script.error_rows
    return script, errors


def build():
    config.logger.info('Building the project.')
    script, errors = get_script()
    if errors:
        for error in errors:
            config.logger.error(error)
        return
    with zipfile.ZipFile(config.BUILD_PATH, 'w') as z:
        for file in os.listdir(config.MEDIA_PATH):
            z.write(os.path.join(config.MEDIA_PATH, file), os.path.join('Media', file))
        z.writestr('script.json', script.seriliazed_tg_script.model_dump_json().encode('utf-8'))
    config.logger.info('Successfully built the project.')


if __name__ == '__main__':
    build()
