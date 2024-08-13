def extract_yab_json(fileobj, keywords, comment_tags, options):
    import json

    content = json.load(fileobj)
    messages = []

    settings = content.get('settings', {})
    reactions = settings.get('reactions', {})
    tech_messages = settings.get('tech_messages', {})
    nodes = content.get('nodes', {})

    for key, value in reactions.items():
        if not value:
            continue
        messages += [(0, '', item, ['reaction', key]) for item in value]

    for key, value in tech_messages.items():
        if not value:
            continue
        messages.append((0, '', value, ['tech_message', key]))

    def recursive_extract(data, node_name: str, is_option=False):
        if isinstance(data, dict):
            for key, value in data.items():
                if key == 'text':
                    if not value:
                        continue
                    messages.append((0, '', value, [
                        f'node: {node_name}',
                        'option' if is_option else 'msg',
                    ]))
                elif key == 'speaker':
                    if not value:
                        continue
                    messages.append((0, '', value, [
                        f'node: {node_name}',
                        'speaker_name',
                    ]))
                recursive_extract(value, node_name)
        elif isinstance(data, list):
            for item in data:
                recursive_extract(item, node_name, is_option=True)

    for node_name, node in nodes.items():
        checkpoint_name = node.get('checkpoint_name')
        if checkpoint_name:
            messages.append((0, '', checkpoint_name, ['checkpoint_name', node_name]))
        flow = node.get('flow', {})
        recursive_extract(flow, node_name)

    return messages
