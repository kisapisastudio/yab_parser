from yab_parser import builder, checker, config
from yab_parser.schemas.script import ScriptInfo
import os
import zipfile
from babel.messages.frontend import CommandLineInterface
import sys


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


def update_translation(native_lang: str):
    with open('babel.cfg', 'w') as f:
        f.write(config.BABEL_CFG)

    os.path.isdir(config.TRANSLATION_PATH) or os.mkdir(config.TRANSLATION_PATH)
    cli = CommandLineInterface()
    sys.argv = [
        'pybabel', 'extract',
        '-F', 'babel.cfg',  # ваш конфигурационный файл
        '-o', os.path.join(config.TRANSLATION_PATH, 'messages.pot'),  # выходной файл
        '.'
    ]
    cli.run(sys.argv)
    for lang in set(config.SUPPORTED_LANGUAGES) - {native_lang}:
        if not os.path.isdir(os.path.join(config.TRANSLATION_PATH, lang)):
            sys.argv = [
                'pybabel', 'init',
                '-i', os.path.join(config.TRANSLATION_PATH, 'messages.pot'),
                '-d', os.path.join(config.TRANSLATION_PATH),
                '-l', lang
            ]
            cli.run(sys.argv)
    sys.argv = [
        'pybabel', 'update',
        '-i', os.path.join(config.TRANSLATION_PATH, 'messages.pot'),
        '-d', os.path.join(config.TRANSLATION_PATH),
    ]
    cli.run(sys.argv)
    sys.argv = [
        'pybabel', 'compile',
        '-d', os.path.join(config.TRANSLATION_PATH),
    ]
    cli.run(sys.argv)

    os.remove('babel.cfg')


def build():
    config.logger.info('Building the project.')
    script, errors = get_script()
    if errors:
        for error in errors:
            config.logger.error(error)
        return

    with open('script.json', 'w') as f:
        f.write(script.seriliazed_tg_script.model_dump_json())

    update_translation(script.settings.default_settings.native_language)

    with zipfile.ZipFile(config.BUILD_PATH, 'w') as z:
        for file in os.listdir(config.MEDIA_PATH):
            z.write(os.path.join(config.MEDIA_PATH, file), os.path.join('Media', file))
        for root, _, files in os.walk(config.TRANSLATION_PATH):
            for file in files:
                file_path = os.path.join(root, file)
                z.write(file_path, file_path)
        z.write('script.json', 'script.json')

    os.remove('script.json')

    with open(config.BUILD_INFO_PATH, 'w') as f:
        f.write(ScriptInfo(
            start_node_name=script.seriliazed_tg_script.start_node,
            all_node_names=list(script.seriliazed_tg_script.nodes.keys()),
            availble_paths=script.paths,
        ).model_dump_json())
    config.logger.info('Successfully built the project.')


if __name__ == '__main__':
    build()
