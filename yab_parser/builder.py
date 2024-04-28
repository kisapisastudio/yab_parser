from lark import Lark, Transformer, Tree, Token, Visitor, exceptions
from lark.indenter import Indenter
from lark.visitors import Interpreter


import csv
import re
import os
import yaml
from mimetypes import guess_type
from bs4 import BeautifulSoup
from uuid import uuid4

from yab_parser import config, schemas


class ExpressionSerializer(Transformer):
    def __init__(self):
        super().__init__()

    def add(self, children):
        result = schemas.script.Expression(
            exp_type=schemas.script.ExpressionType.add,
            value=children
        )
        return result

    def subtract(self, children):
        result = schemas.script.Expression(
            exp_type=schemas.script.ExpressionType.subtract,
            value=children
        )
        return result

    def multiply(self, children):
        result = schemas.script.Expression(
            exp_type=schemas.script.ExpressionType.multiply,
            value=children
        )
        return result

    def divide(self, children):
        result = schemas.script.Expression(
            exp_type=schemas.script.ExpressionType.divide,
            value=children
        )
        return result

    def modulo(self, children):
        result = schemas.script.Expression(
            exp_type=schemas.script.ExpressionType.modulo,
            value=children
        )
        return result

    def number(self, children):
        if children[0].type == 'INT':
            return int(children[0].value)
        return float(children[0].value)

    def common_var_name(self, children):
        return schemas.script.Var(name=children[0].value)

    def node_var_name(self, children):
        return schemas.script.Var(name=children[0].value)


class ConditionSerializer(Transformer):
    def __init__(self):
        super().__init__()

    def and_op(self, children):
        return schemas.script.Condition(
            cond_type=schemas.script.ConditionType.and_op,
            value=children
        )

    def or_op(self, children):
        return schemas.script.Condition(
            cond_type=schemas.script.ConditionType.or_op,
            value=children
        )

    def not_op(self, children):
        return schemas.script.Condition(
            cond_type=schemas.script.ConditionType.not_op,
            value=children
        )

    def eq(self, children):
        return schemas.script.Condition(
            cond_type=schemas.script.ConditionType.eq,
            value=children
        )

    def ne(self, children):
        return schemas.script.Condition(
            cond_type=schemas.script.ConditionType.ne,
            value=children
        )

    def lt(self, children):
        return schemas.script.Condition(
            cond_type=schemas.script.ConditionType.lt,
            value=children
        )

    def gt(self, children):
        return schemas.script.Condition(
            cond_type=schemas.script.ConditionType.gt,
            value=children
        )

    def le(self, children):
        return schemas.script.Condition(
            cond_type=schemas.script.ConditionType.le,
            value=children
        )

    def ge(self, children):
        return schemas.script.Condition(
            cond_type=schemas.script.ConditionType.ge,
            value=children
        )

    def calculate(self, children):
        return ExpressionSerializer().transform(Tree(Token('RULE', 'calculate'), children)).children[0]

    def value(self, children):
        child = children[0]
        if isinstance(child, schemas.script.Var):
            return child
        if isinstance(child, Tree):
            return child.children[0].value


class BranchSerializer(Interpreter):
    def __init__(self):
        super().__init__()
        self._flow = {}
        self.msg_types = {
            'text_message': schemas.script.MessageType.text,
            'video_message': schemas.script.MessageType.video,
            'photo_message': schemas.script.MessageType.photo,
            'voice_message': schemas.script.MessageType.voice,
            'video_note_message': schemas.script.MessageType.video_note
        }
        self.next_uuid = ''
        self.last_uid = ''
        self.exist_uids = {}

    def line(self, tree):
        line_type = tree.children[0].data.value
        if line_type in [
            'jump_command',
            'wait_command',
            'reaction_command',
            'var_command',
            'status_sending_command',
            'back_to_flow_command'
        ]:
            self._set_uidds()
            self._flow[self.last_uid] = self._get_command(tree.children[0])
            self._flow[self.last_uid].next_line_id = self.next_uuid
        elif line_type in ['text_message', 'video_message', 'photo_message', 'voice_message', 'video_note_message']:
            self._set_uidds(tree.children[0].children)
            self._flow[self.last_uid], addition_flow = self._get_message(tree.children, line_type)
            self._flow.update(addition_flow)
            self._flow[self.last_uid].next_line_id = self.next_uuid
        elif line_type == 'condition_block':
            self._set_uidds()
            self._flow[self.last_uid], addition_flow = self._get_condition_block(tree.children[0])
            self._flow.update(addition_flow)
            self._flow[self.last_uid].next_line_id = self.next_uuid

    def _set_out_link(self, link):
        links = self._flow.keys()
        for key in self._flow:
            if isinstance(self._flow[key], schemas.script.Message) and self._flow[key].options:
                for option in self._flow[key].options:
                    if option.link in links:
                        continue
                    option.link = link
            elif isinstance(self._flow[key], schemas.script.FlowControl):
                if self._flow[key].if_block.link in links:
                    continue
                self._flow[key].if_block.link = link

                for elif_block in self._flow[key].elif_blocks:
                    if elif_block.link in links:
                        continue
                    elif_block.link = link

                if self._flow[key].else_block:
                    if self._flow[key].else_block.link in links:
                        continue
                    self._flow[key].else_block.link = link

            if self._flow[key].next_line_id in links:
                continue
            self._flow[key].next_line_id = link

    def _postprocess(self):
        flow = self._flow.copy()
        self._flow = {}
        for key in flow:
            true_key = self.exist_uids.get(key, key)
            flow[key].next_line_id = self.exist_uids.get(flow[key].next_line_id, flow[key].next_line_id)
            if isinstance(flow[key], schemas.script.Message):
                for option in flow[key].options:
                    option.link = self.exist_uids.get(option.link, option.link)
            elif isinstance(flow[key], schemas.script.FlowControl):
                if flow[key].if_block:
                    flow[key].if_block.link = self.exist_uids.get(flow[key].if_block.link, flow[key].if_block.link)
                for elif_block in flow[key].elif_blocks:
                    elif_block.link = self.exist_uids.get(elif_block.link, elif_block.link)
                if flow[key].else_block:
                    flow[key].else_block.link = self.exist_uids.get(
                        flow[key].else_block.link, flow[key].else_block.link
                    )
            self._flow[true_key] = flow[key]

        for key in self._flow:
            if not self._flow.get(self._flow[key].next_line_id):
                self._flow[key].next_line_id = None

    def _set_uidds(self, children: list = []):
        for child in children:
            if not self.next_uuid:
                break
            if child.data.value == 'line_ident':
                self.exist_uids[self.next_uuid] = child.children[0].value
                break
        self.last_uid = self.next_uuid
        self.next_uuid = str(uuid4())

    def _get_command(self, child):
        command = None
        if child.data.value == 'jump_command':
            node_name = list(child.find_data('node_name'))
            node_name = node_name[0].children[0].value
            command = schemas.script.Command(
                command_type=schemas.script.CommandType.jump,
                args={'node_name': node_name}
            )
        elif child.data.value == 'wait_command':
            seconds = list(child.find_data('seconds'))
            seconds = float(seconds[0].children[0].value)
            command = schemas.script.Command(
                command_type=schemas.script.CommandType.wait,
                args={'seconds': seconds}
            )
        elif child.data.value == 'reaction_command':
            reaction = list(child.find_data('reaction'))
            reaction = reaction[0].children[0].value
            command = schemas.script.Command(
                command_type=schemas.script.CommandType.reaction,
                args={'reaction': reaction}
            )
        elif child.data.value == 'var_command':
            command = self._get_var_command(child.children[0])
        elif child.data.value == 'status_sending_command':
            command = self._get_status_sending_command(child)
        elif child.data.value == 'back_to_flow_command':
            command = schemas.script.Command(
                command_type=schemas.script.CommandType.back_to_flow,
            )
        return command

    def _get_var_command(self, child):
        node_var_name = list(child.find_data('node_var_name'))
        if node_var_name:
            var_name = node_var_name[0].children[0].value
            is_temporary = True
        else:
            var_name = list(child.find_data('common_var_name'))
            var_name = var_name[0].children[0].value
            is_temporary = False

        value = list(child.find_data('value'))
        value = value[0].children[0].children[0].value if value else None
        calculation = list(child.find_data('calculate'))
        if calculation:
            calculation = ExpressionSerializer().transform(calculation[0]).children[0]
        else:
            calculation = None

        if child.data.value == 'set_var':
            var_command = schemas.script.VariableCommand(
                command_type=schemas.script.VariableCommandType.set,
                name=var_name,
                value=value,
                calculation=calculation,
                is_temporary=is_temporary
            )
        elif child.data.value == 'declare_var':
            var_command = schemas.script.VariableCommand(
                command_type=schemas.script.VariableCommandType.declare,
                name=var_name,
                value=value,
                calculation=calculation,
                is_temporary=is_temporary
            )
        return var_command

    def _get_status_sending_command(self, child):
        type_command = child.children[0].data.value
        seconds = list(child.find_data('seconds'))
        seconds = float(seconds[0].children[0].value)

        if type_command == 'typing':
            return schemas.script.Command(
                command_type=schemas.script.CommandType.typing,
                args={'seconds': seconds}
            )
        elif type_command == 'upload_photo':
            return schemas.script.Command(
                command_type=schemas.script.CommandType.upload_photo,
                args={'seconds': seconds}
            )
        elif type_command == 'record_voice':
            return schemas.script.Command(
                command_type=schemas.script.CommandType.record_voice,
                args={'seconds': seconds}
            )
        elif type_command == 'record_video_note':
            return schemas.script.Command(
                command_type=schemas.script.CommandType.record_video_note,
                args={'seconds': seconds}
            )

    def _get_message(self, msg_children, message_type):
        msg = msg_children[0]
        if len(msg_children) == 2:
            options, flow = self._get_options(msg_children[1])
        else:
            options = []
            flow = {}

        media, text, speaker = self._get_message_data(msg.children)

        return schemas.script.Message(
            message_type=self.msg_types[message_type],
            speaker=speaker,
            options=options,
            media=media,
            text=text
        ), flow

    def _get_message_data(self, children):
        media = None
        text = None
        speaker = None
        for child in children:
            if child.data.value == 'media':
                media = child.children[0].value
            elif child.data.value == 'tg_text':
                text = {t.type.lower(): t.value for t in child.children}
            elif child.data.value == 'speaker':
                speaker = child.children[0].value
        return media, text, speaker

    def _get_options(self, options_tree):
        options = []
        flow = {}
        for option in options_tree.children:
            next_options, add_flow = self._get_option(option)
            options.append(next_options)
            flow.update(add_flow)
        return options, flow

    def _get_option(self, option_tree):
        text = None
        condition = None
        flow = {}
        for child in option_tree.children:
            tree_type = child.data.value if isinstance(child.data, Token) else child.data
            start_link = None
            if tree_type == 'tg_text':
                text = {t.type.lower(): t.value for t in child.children}
            elif tree_type == 'if_statement':
                condition = child.children[0].value
            elif tree_type == 'branch':
                branch_serializer = BranchSerializer()
                start_link = str(uuid4())
                branch_serializer.next_uuid = start_link
                branch_serializer.visit(child)
                branch_serializer._postprocess()
                branch_serializer._set_out_link(self.next_uuid)
                flow = branch_serializer._flow
                start_link = branch_serializer.exist_uids.get(start_link, start_link)
            elif tree_type == 'conditions':
                condition = ConditionSerializer().transform(child).children[0]
        return schemas.script.Option(
            text=text,
            condition=condition,
            link=start_link if start_link else self.next_uuid
        ), flow

    def _get_condition_block(self, condition_tree):
        condition_block = schemas.script.FlowControl()
        additional_flow = {}
        for child in condition_tree.children:
            if len(child.children) == 2:
                branch_serializer = BranchSerializer()
                start_link = str(uuid4())
                branch_serializer.next_uuid = start_link
                branch_serializer.visit(child.children[1])
                branch_serializer._postprocess()
                branch_serializer._set_out_link(self.next_uuid)
                additional_flow.update(branch_serializer._flow)
                start_link = branch_serializer.exist_uids.get(start_link, start_link)
            else:
                start_link = None
            flow_control_element = schemas.script.FlowControlElement(
                link=start_link
            )

            if child.data == 'if_block':
                flow_control_element.condition = ConditionSerializer().transform(child.children[0]).children[0]
                condition_block.if_block = flow_control_element
            elif child.data == 'elif_block':
                flow_control_element.condition = ConditionSerializer().transform(child.children[0]).children[0]
                condition_block.elif_blocks.append(flow_control_element)
            elif child.data == 'else_block':
                condition_block.else_block = flow_control_element

        return condition_block, additional_flow


class TgSerializer(Interpreter):
    def __init__(self):
        super().__init__()
        self._script = schemas.script.Node()

    def header(self, tree):
        for child in tree.children:
            if child.data == 'title':
                self._script.title = child.children[0].value.strip()
            elif child.data == 'checkpoint_name':
                self._script.checkpoint_name = self._get_translation_text(child.children)
            elif child.data == 'start_on_command':
                self._script.start_on_command = child.children[0].value.strip()
            elif child.data == 'reaction':
                self._script.reaction = child.children[0].value.strip()
            elif child.data == 'wait':
                self._script.wait = child.children[0].value.strip()
            elif child.data == 'time':
                self._script.time = child.children[0].value.strip()
            elif child.data == 'time_for_status':
                self._script.time_for_status = child.children[0].value.strip()

    def branch(self, tree):
        branch_serializer = BranchSerializer()
        branch_serializer.visit(tree)
        branch_serializer._postprocess()
        self._script.flow = branch_serializer._flow

    def _get_translation_text(self, children):
        return {str(child.type).lower(): child.value.strip().strip('"') for child in children if child.value.strip()}


class TgTransformer(Transformer):
    def __init__(
        self,
        translation: dict[str, dict[str, str]],
        languges: list[str]
    ) -> None:
        super().__init__()
        self._header_params = [
            'title', 'checkpoint_name', 'start_on_command', 'reaction', 'wait', 'time', 'time_for_status'
        ]
        self._translation = translation
        self.text_parser = self._get_lark_text_parser()
        self._new_translation = {}
        self._error_rows = []
        self._languges = languges

    def line(self, children):
        for child in children:
            if child.data.value == 'options':
                self.line(child.children)
                continue
            ident = list(child.find_data('line_ident'))
            ident = ident[0].children[0].value if ident else None
            speaker_tree = list(child.find_data('speaker'))
            if speaker_tree:
                speaker_tree[0].set(
                    Token('RULE', 'tg_speaker'),
                    self._make_tg_and_tr_text(speaker_tree[0].children, ident)
                )
            formated_text_tree = list(child.find_data('formated_text'))
            if formated_text_tree:
                formated_text_tree[0].set(
                    Token('RULE', 'tg_text'),
                    self._make_tg_and_tr_text(formated_text_tree[0].children, ident)
                )
        return Tree(Token('RULE', 'line'), children)

    def header(self, children):
        result = []
        for param_tree in children:
            param_name = list(param_tree.find_data('header_param_name'))
            param_name = param_name[0].children[0].value
            value = list(param_tree.find_data('header_param_value'))
            value = value[0].children[0].value
            if param_name not in self._header_params:
                continue
            if param_name == 'checkpoint_name':
                if self._translation.get(param_name):
                    self._new_translation[param_name] = self._translation[param_name]
                else:
                    self._new_translation[param_name] = {config.SUPPORTED_LANGUAGES[0]: value}
                    self._new_translation[param_name].update({lang: '' for lang in config.SUPPORTED_LANGUAGES[1:]})
                cp_children = [Token(config.SUPPORTED_LANGUAGES[0].upper(), value)]
                for lang in config.SUPPORTED_LANGUAGES[1:]:
                    if self._new_translation[param_name].get(lang):
                        cp_children.append(Token(lang.upper(), self._new_translation[param_name][lang]))
                result.append(Tree(Token('RULE', param_name), cp_children))
                continue
            result.append(Tree(Token('RULE', param_name), [Token('VALUE', value)]))
        return Tree(Token('RULE', 'header'), result)

    def _make_tg_and_tr_text(self, children, ident=None):
        tg_text, tr_text, used_vars = self._to_tg_text(children, ident)
        result = [Token(config.SUPPORTED_LANGUAGES[0], tg_text)]
        if ident:
            is_ident_in_translation = self._translation.get(ident)
            if is_ident_in_translation:
                is_base_text_eq_tg_text = self._translation[ident].get(
                    config.SUPPORTED_LANGUAGES[0]
                ).strip().lower() == tr_text.strip().lower()
            else:
                is_base_text_eq_tg_text = False
            is_text_not_empty = tg_text.strip()
            if is_ident_in_translation and is_base_text_eq_tg_text:
                self._new_translation[ident] = self._translation[ident]
                for lang in config.SUPPORTED_LANGUAGES[1:]:
                    if self._translation[ident].get(lang) and self._translation[ident][lang].strip():
                        tr_tg_text = self._parse_text(
                            self._new_translation[ident][lang],
                            ident,
                            used_vars,
                        )
                        result.append(Token(lang.upper(), tr_tg_text))
            elif is_text_not_empty:
                if len(self._languges) > 1:
                    self._error_rows.append(
                        f'The line {ident} has no translation.'
                    )
                self._new_translation[ident] = {config.SUPPORTED_LANGUAGES[0]: tr_text}
                self._new_translation[ident].update({lang: '' for lang in config.SUPPORTED_LANGUAGES[1:]})
        return result

    def _to_tg_text(self, children, ident=None):
        tg_text_row = []
        tr_text_row = []
        used_vars = set()
        for child in children:
            if child.data.value == 'text':
                tg_text_row.append(child.children[0].value)
                tr_text_row.append(child.children[0].value)
            elif child.data.value == 'tag':
                tg_text_row.append(self._add_tg_tag(child.children[0]))
                tr_text_row.append(self._add_tr_tag(child.children[0]))
            elif child.data.value == 'inline_var':
                common_var_name = list(child.find_data('common_var_name'))
                if common_var_name:
                    tg_text_row.append('{' + common_var_name[0].children[0].value + '}')
                    tr_text_row.append('{' + common_var_name[0].children[0].value + '}')
                    used_vars.add(common_var_name[0].children[0].value)
                    continue
                node_var_name = list(child.find_data('node_var_name'))
                if node_var_name:
                    tg_text_row.append('{' + node_var_name[0].children[0].value + '}')
                    tr_text_row.append('{' + node_var_name[0].children[0].value + '}')
                    used_vars.add(node_var_name[0].children[0].value)
                    continue
            elif child.data.value == 'escaped_char':
                tr_text_row.append('\\' + child.children[0].value)
                if child.children[0].value in ['{', '}']:
                    tg_text_row.append(child.children[0].value*2)
                    continue
                elif child.children[0].value == '<':
                    tg_text_row.append('&lt;')
                    continue
                elif child.children[0].value == '>':
                    tg_text_row.append('&gt;')
                    continue
                tg_text_row.append(child.children[0].value)
        soup = BeautifulSoup(''.join(tg_text_row), 'html.parser')
        corrected_tg_text = str(soup)
        return corrected_tg_text, ''.join(tr_text_row), used_vars

    def _parse_text(self, text: str, ident: str, used_vars: set[str]):
        parsed_text = self.text_parser.parse(text, on_error=self._make_error_parser_func(ident))
        tg_text, _, used_tr_vars = self._to_tg_text(parsed_text.children)
        if used_vars != used_tr_vars:
            self._error_rows.append(
                f'The translation of the node {ident} uses different variables than the original text.'
            )
        return tg_text

    def _get_lark_text_parser(self) -> Lark:
        with open(config.LARK_GRAMMAR_PATH, 'r') as f:
            grammar = f.read()
        return Lark(grammar, parser='lalr', start='formated_text', debug=True)

    def _make_error_parser_func(self, ident: str):
        def error_func(error: exceptions.LarkError, ident: str = ident):
            if isinstance(error, exceptions.UnexpectedToken):
                self._error_rows.append(
                    f'Error ident {ident}: expected tokens {error.expected} but got "{error.token}"'
                )
                return True
            return False
        return error_func

    def _add_tg_tag(self, tag_tree: Tree):
        tag_type = tag_tree.data.value
        if tag_type == 'line_break_tag':
            return '\n'
        elif tag_type == 'open_link_tag':
            url_tree = list(tag_tree.find_data('url'))
            if url_tree:
                common_var_name = list(url_tree[0].find_data('common_var_name'))
                node_var_name = list(url_tree[0].find_data('node_var_name'))
                if common_var_name:
                    url = '{' + common_var_name[0].children[0].value + '}'
                elif node_var_name:
                    url = '{' + node_var_name[0].children[0].value + '}'
                else:
                    url = url_tree[0].children[0].value
                return f'<a href="{url}">'
            return '<a href="#">'
        elif tag_type == 'close_link_tag':
            return '</a>'
        elif tag_type == 'colon_tag':
            return ':'
        elif tag_type == 'usd_tag':
            return '$'
        elif tag_type == 'open_bold_tag':
            return '<b>'
        elif tag_type == 'close_bold_tag':
            return '</b>'
        elif tag_type == 'open_underline_tag':
            return '<u>'
        elif tag_type == 'close_underline_tag':
            return '</u>'
        elif tag_type == 'open_strike_tag':
            return '<s>'
        elif tag_type == 'close_strike_tag':
            return '</s>'
        elif tag_type == 'open_italic_tag':
            return '<i>'
        elif tag_type == 'close_italic_tag':
            return '</i>'
        elif tag_type == 'open_spoiler_tag':
            return '<tg-spoiler>'
        elif tag_type == 'close_spoiler_tag':
            return '</tg-spoiler>'
        elif tag_type == 'open_monospace_tag':
            return '<code>'
        elif tag_type == 'close_monospace_tag':
            return '</code>'
        elif tag_type == 'close_all_tags':
            return ''

    def _add_tr_tag(self, tag_tree: Tree):
        tag_type = tag_tree.data.value
        if tag_type == 'line_break_tag':
            return '[br/]'
        elif tag_type == 'open_link_tag':
            url_tree = list(tag_tree.find_data('url'))
            if url_tree:
                common_var_name = list(url_tree[0].find_data('common_var_name'))
                node_var_name = list(url_tree[0].find_data('node_var_name'))
                if common_var_name:
                    url = common_var_name[0].children[0].value
                elif node_var_name:
                    url = node_var_name[0].children[0].value
                else:
                    url = url_tree[0].children[0].value
                return f'[link {url}]'
            return '[link #]'
        elif tag_type == 'close_link_tag':
            return '[/link]'
        elif tag_type == 'colon_tag':
            return '[cl/]'
        elif tag_type == 'usd_tag':
            return '[usd/]'
        elif tag_type == 'open_bold_tag':
            return '[b]'
        elif tag_type == 'close_bold_tag':
            return '[/b]'
        elif tag_type == 'open_underline_tag':
            return '[u]'
        elif tag_type == 'close_underline_tag':
            return '[/u]'
        elif tag_type == 'open_strike_tag':
            return '[s]'
        elif tag_type == 'close_strike_tag':
            return '[/s]'
        elif tag_type == 'open_italic_tag':
            return '[i]'
        elif tag_type == 'close_italic_tag':
            return '[/i]'
        elif tag_type == 'open_spoiler_tag':
            return '[spoiler]'
        elif tag_type == 'close_spoiler_tag':
            return '[/spoiler]'
        elif tag_type == 'open_monospace_tag':
            return '[ms]'
        elif tag_type == 'close_monospace_tag':
            return '[/ms]'
        elif tag_type == 'close_all_tags':
            return '[/]'


class HeaderVisitor(Visitor):
    def __init__(self):
        self.title = None
        self.is_start_node = False
        self.is_title = False

    def header_param(self, tree: Tree):
        param_name = tree.children[0].children[0].value
        if param_name == 'title':
            self.title = tree.children[1].children[0].value
            self.is_title = True
        elif param_name == 'is_entry_point' and tree.children[1].children[0].value == 'true':
            self.is_start_node = True


class NodesVisitor(Visitor):
    def __init__(self):
        self.all_nodes = {}
        self.start_node = None
        self.error_rows = []

    def node(self, tree: Tree):
        header = tree.children[0]
        header_visitor = HeaderVisitor()
        header_visitor.visit(header)
        if not header_visitor.is_title:
            self.error_rows.append('The node does not have a title.')
        self.all_nodes[header_visitor.title] = tree
        if header_visitor.is_start_node:
            self.start_node = header_visitor.title
        elif header_visitor.is_start_node and self.start_node:
            self.error_rows.append(
                f'There are more than one start nodes - {header_visitor.title} and {self.start_node}'
            )


class FlowVisitor(Visitor):
    def __init__(self):
        self.declared_vars = set()
        self.used_vars = set()
        self.declared_vars_in_node = set()
        self.used_vars_in_node = set()
        self.node_links = set()
        self.used_media = set()

    def jump_command(self, tree: Tree):
        node_name_param = list(tree.find_data('node_name'))
        if node_name_param:
            node_name = node_name_param[0].children[0]
            self.node_links.add(node_name.value)

    def inline_var(self, tree: Tree):
        common_var_name = list(tree.find_data('common_var_name'))
        if common_var_name:
            var_name = common_var_name[0].children[0]
            self.used_vars.add(var_name.value)
            return
        node_var_name = list(tree.find_data('node_var_name'))
        if node_var_name:
            var_name = node_var_name[0].children[0]
            self.used_vars_in_node.add(var_name.value)
            return

    def set_var(self, tree: Tree):
        common_var_name = list(tree.find_data('common_var_name'))
        if common_var_name:
            var_name = common_var_name[0].children[0]
            self.used_vars.add(var_name.value)
            return
        node_var_name = list(tree.find_data('node_var_name'))
        if node_var_name:
            var_name = node_var_name[0].children[0]
            self.used_vars_in_node.add(var_name.value)
            return

    def declare_var(self, tree: Tree):
        common_var_name = list(tree.find_data('common_var_name'))
        if common_var_name:
            var_name = common_var_name[0].children[0]
            self.declared_vars.add(var_name.value)
            return
        node_var_name = list(tree.find_data('node_var_name'))
        if node_var_name:
            var_name = node_var_name[0].children[0]
            self.declared_vars_in_node.add(var_name.value)
            return

    def media(self, tree: Tree):
        media_name = tree.children[0]
        self.used_media.add(media_name.value)


class YabScriptChecker():
    def __init__(self, yab_script: 'YabScriptBuilder'):
        self.start_node = None
        self.sep_nodes = {}
        self.error_rows = []
        self.start_node = None
        self.paths = []
        self.media = set()
        self._check_nodes(yab_script)
        self._check_flow()

    def _check_nodes(self, yab_script: 'YabScriptBuilder'):
        nodes_visitor = NodesVisitor()
        nodes_visitor.visit(yab_script.parsed_script)
        self.sep_nodes = nodes_visitor.all_nodes
        self.start_node = nodes_visitor.start_node
        if not self.start_node:
            self.error_rows.append('The start node is not defined.')
            self.start_node = list(self.sep_nodes.keys())[0]
        self.error_rows += nodes_visitor.error_rows

    def _check_flow(self):
        visited_nodes = {}
        for node in self.sep_nodes:
            visitor = FlowVisitor()
            visitor.visit(self.sep_nodes[node])
            visited_nodes[node] = visitor
        self.paths = self._find_paths(visited_nodes, self.start_node)
        for path in self.paths:
            self._check_vars(visited_nodes, path)
        for node in visited_nodes:
            self.media.update(visited_nodes[node].used_media)

    def _find_paths(self, nodes: dict[str, FlowVisitor], start_node: str, path=[]):
        path = path + [start_node]

        if start_node not in nodes:
            self.error_rows.append(f'The node {start_node} does not exist.')
            return [path]
        if not nodes[start_node].node_links:
            return [path]

        paths = []
        for node_link in nodes[start_node].node_links:
            if node_link not in path:
                newpaths = self._find_paths(nodes, node_link, path)
                for newpath in newpaths:
                    paths.append(newpath)
        return paths

    def _check_vars(self, nodes: dict[str, FlowVisitor], path: list[str]):
        declared_vars = set()
        for node_name in path:
            node_data = nodes.get(node_name)
            if not node_data:
                self.error_rows.append(f'The node {node_name} does not exist. The path = {" -> ".join(path)}')
                continue
            for declaration in node_data.declared_vars:
                if declaration in declared_vars:
                    self.error_rows.append(
                        ' '.join([
                            f'Node - {node_name}.',
                            f'The variable {declaration} is already declared',
                            f'in the path = {" -> ".join(path)}'
                        ])
                    )
                declared_vars.add(declaration)
            for usage_var in node_data.used_vars:
                if usage_var not in declared_vars:
                    self.error_rows.append(
                        ' '.join([
                            f'Node - {node_name}.',
                            f'The variable {usage_var} is not declared',
                            f'in the path = {" -> ".join(path)}'
                        ])
                    )
            for local_var in node_data.used_vars_in_node:
                if local_var not in node_data.declared_vars_in_node:
                    self.error_rows.append(
                        ' '.join([
                            f'Node - {node_name}.',
                            f'The variable {local_var} is not declared',
                            f'in the node {node_name}'
                        ])
                    )


class YabScriptBuilder():
    def __init__(
        self,
        story_paths: list[str | os.PathLike],
        setting_path: str | os.PathLike,
    ):
        config.logger.info('Parsing the script.')
        self.error_rows = []
        self.parser = self._get_lark_parser()
        self.settings = self._get_settings(setting_path)
        self.full_script = ''
        self.scripts_with_idents = {}
        self.start_node = None
        self.sep_nodes = {}
        self.tg_script = {}
        self.paths = []
        self.media = set()

        if self.error_rows:
            return
        for path in story_paths:
            with open(path, 'r') as f:
                script_rows = self._add_idents(f.readlines())
                try:
                    self.parser.parse(
                        ''.join(script_rows),
                        on_error=self._make_error_parser_func(path.split('/')[-1])
                    )
                except exceptions.LarkError:
                    self.error_rows.append(f'The script {path} is incorrect.')
                else:
                    self.full_script += ''.join(script_rows)
                    self.scripts_with_idents[path] = script_rows
        if self.error_rows:
            return
        self.parsed_script = self.parser.parse(self.full_script)
        self._check()
        self.translation = self._get_translation()
        for node in self.sep_nodes:
            tg_transformer = TgTransformer(
                self.translation.get(node, {}),
                self.settings.default_settings.languages.keys()
            )
            self.tg_script[node] = tg_transformer.transform(self.sep_nodes[node])
            self.error_rows += tg_transformer._error_rows
            self._add_translation_file(node, tg_transformer._new_translation)
        self._serilize_tg_script()
        self._post_process()

    def _add_idents(self, script_rows: list[str]) -> list[str]:
        is_body = False
        line_re = re.compile(r'^[^<\/\n].+')
        ident_re = re.compile(r'(?<!\\)#\s*line\s*:\s*[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}')
        comment_re = r'(?<!\\)//'
        tags_re = r'(?<!\\)\[.*?\s*(?<!\\)]'
        idented_script_rows = []
        for row in script_rows:
            if row.strip() == '---':
                is_body = True
                idented_script_rows.append(row)
                continue
            elif row.strip() == '===':
                is_body = False
                idented_script_rows.append(row)
                continue
            if not is_body:
                idented_script_rows.append(row)
                continue

            base_line_without_tags = re.sub(tags_re, '', row)
            _, *comments = re.split(comment_re, base_line_without_tags)
            comment = f'//{"//".join(comments)}'.strip() if comments else ''
            base_line = row.replace('\n', '')
            base_line = base_line.strip(comment)

            if line_re.match(row.strip()) and not ident_re.search(row):
                ident = str(uuid4())
                idented_script_rows.append(
                    f'{base_line} #line:{ident}' + comment + '\n'
                )
            elif ident_re.search(row):
                ident = ident_re.search(row)
                idented_script_rows.append(row)
            else:
                idented_script_rows.append(row)
        return idented_script_rows

    def _get_lark_parser(self) -> Lark:
        with open(config.LARK_GRAMMAR_PATH, 'r') as f:
            grammar = f.read()

        class TreeIndenter(Indenter):
            NL_type = '_NL'
            OPEN_PAREN_types = []
            CLOSE_PAREN_types = []
            INDENT_type = '_INDENT'
            DEDENT_type = '_DEDENT'
            tab_len = 4

        return Lark(grammar, parser='lalr', postlex=TreeIndenter(), start='nodes', debug=True)

    def _check(self):
        check_visitor = YabScriptChecker(self)
        self.error_rows += check_visitor.error_rows
        self.sep_nodes = check_visitor.sep_nodes
        self.start_node = check_visitor.start_node
        self.paths = check_visitor.paths
        self.media = check_visitor.media

    def _get_settings(self, setting_path: str | os.PathLike) -> schemas.settings.ScriptSettings:
        with open(setting_path, 'r') as f:
            try:
                settings = yaml.safe_load(f)
            except Exception as e:
                self.error_rows.append(f'The settings file is incorrect: {e}')
                return
        try:
            result = schemas.settings.ScriptSettings(**settings)
        except Exception as e:
            for error in e.errors():
                error_message = f'The settings are incorrect: {error.get("msg")}'
                if e.errors()[0].get('loc'):
                    error_message += f' in {" -> ".join(error.get("loc"))}.'
                self.error_rows.append(error_message)
            return
        return result

    def _make_error_parser_func(self, file_name: str):
        def error_func(error: exceptions.LarkError, file_name: str = file_name):
            if isinstance(error, exceptions.UnexpectedToken):
                self.error_rows.append(
                    ' '.join([
                        f'Error in {file_name} line {error.line}',
                        f'column {error.column}: expected tokens {error.expected}',
                        f'but got "{error.token}"',
                    ])
                )
                return True
            return False
        return error_func

    def _post_process(self):
        self._change_source()
        self._add_media()

    def _change_source(self):
        for path in self.scripts_with_idents:
            with open(path, 'w') as f:
                f.writelines(self.scripts_with_idents[path])

    def _add_media(self):
        exist_media = set(os.listdir(config.MEDIA_PATH))
        for_deletion = exist_media - self.media
        new_media = self.media - exist_media

        for media in for_deletion:
            os.remove(os.path.join(config.MEDIA_PATH, media))

        for media in new_media:
            if not guess_type(media)[0]:
                media_content = b''
            elif guess_type(media)[0] == 'image/jpeg':
                with open(config.EXAMPLE_JPG_PATH, 'rb') as f:
                    media_content = f.read()
            elif guess_type(media)[0] == 'image/png':
                with open(config.EXAMPLE_PNG_PATH, 'rb') as f:
                    media_content = f.read()
            elif guess_type(media)[0] == 'audio/ogg':
                with open(config.EXAMPLE_OOG_PATH, 'rb') as f:
                    media_content = f.read()
            elif guess_type(media)[0] == 'video/mp4':
                with open(config.EXAMPLE_MP4_PATH, 'rb') as f:
                    media_content = f.read()
            elif guess_type(media)[0] == 'video/quicktime':
                with open(config.EXAMPLE_MOV_PATH, 'rb') as f:
                    media_content = f.read()
            else:
                media_content = b''

            with open(os.path.join(config.MEDIA_PATH, media), 'wb') as f:
                f.write(media_content)

    def _get_translation(self):
        result = {}
        if not os.path.exists(config.TRANSLATION_PATH):
            os.mkdir(config.TRANSLATION_PATH)
            return result
        file_to_delete = set(
            os.listdir(config.TRANSLATION_PATH)
        ) - set(
            [f'{node_name}.csv' for node_name in self.sep_nodes.keys()]
        )
        for file in file_to_delete:
            os.remove(os.path.join(config.TRANSLATION_PATH, file))
        for file in os.listdir(config.TRANSLATION_PATH):
            with open(os.path.join(config.TRANSLATION_PATH, file), 'r') as f:
                reader = csv.DictReader(f)
                result[file.split('.')[-2]] = {
                    row['ident']: {k: v for k, v in row.items() if k != 'ident'} for row in reader
                }
        return result

    def _add_translation_file(self, node_name: str, translation: dict[str, dict[str, str]]):
        with open(os.path.join(config.TRANSLATION_PATH, f'{node_name}.csv'), 'w') as f:
            writer = csv.DictWriter(f, fieldnames=['ident']+config.SUPPORTED_LANGUAGES)
            writer.writeheader()
            for ident in translation:
                row = {'ident': ident}
                for lang in translation[ident]:
                    row[lang] = translation[ident][lang]
                writer.writerow(row)

    def _serilize_tg_script(self):
        self.seriliazed_tg_script = schemas.script.Script(
            settings=self.settings,
            start_node=self.start_node,
        )
        for node_name in self.tg_script:
            tg_serializer = TgSerializer()
            tg_serializer.visit(self.tg_script[node_name])
            self.seriliazed_tg_script.nodes[node_name] = tg_serializer._script
