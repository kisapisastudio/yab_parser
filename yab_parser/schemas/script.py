from pydantic import BaseModel, field_validator
from yab_parser.schemas.settings import ScriptSettings
from enum import Enum
from typing import Union


class MessageType(str, Enum):
    text = 'text'
    photo = 'photo'
    video = 'video'
    voice = 'voice'
    video_note = 'video_note'


class CommandType(str, Enum):
    back_to_flow = 'back_to_flow'
    record_voice = 'record_voice'
    typing = 'typing'
    upload_photo = 'upload_photo'
    upload_video = 'upload_video'
    record_video_note = 'record_video_note'
    wait = 'wait'
    reaction = 'reaction'
    jump = 'jump'


class VariableCommandType(str, Enum):
    declare = 'declare'
    set = 'set'


class ExpressionType(str, Enum):
    add = 'add'
    subtract = 'subtract'
    multiply = 'multiply'
    divide = 'divide'
    modulo = 'modulo'


class ConditionType(str, Enum):
    and_op = 'and'
    or_op = 'or'
    not_op = 'not'
    eq = '=='
    ne = '!='
    lt = '<'
    gt = '>'
    le = '<='
    ge = '>='


class Var(BaseModel):
    name: str


class Condition(BaseModel):
    cond_type: ConditionType
    value: list[Union['Expression', 'Condition', Var, int, float, bool]] = []

    @field_validator('value', mode='before')
    @classmethod
    def get_value(cls, v):
        result = []
        for item in v:
            if isinstance(item, str):
                if item.lower().strip() == 'true':
                    result.append(True)
                elif item.lower().strip() == 'false':
                    result.append(False)
                try:
                    result.append(int(item))
                    continue
                except ValueError:
                    pass
                try:
                    result.append(float(item))
                    continue
                except ValueError:
                    pass
            else:
                result.append(item)
        return v


class Expression(BaseModel):
    exp_type: ExpressionType
    value: list[Union['Expression', int, float, Var]] = []


class Command(BaseModel):
    command_type: CommandType
    args: dict | None = None
    next_line_id: str | None = None


class Option(BaseModel):
    text: str
    condition: Condition | None = None
    link: str | None = None

    @field_validator('text')
    @classmethod
    def remove_empty_text(cls, v):
        return v.strip()


class Message(BaseModel):
    message_type: MessageType
    speaker: str | None = None
    options: list[Option] = []
    media: str | None = None
    text: str | None = None
    next_line_id: str | None = None

    @field_validator('text', 'speaker')
    @classmethod
    def remove_empty_text(cls, v):
        if v is None:
            return v
        return v.strip()


class VariableCommand(BaseModel):
    command_type: VariableCommandType
    name: str
    value: bool | int | float | str | None = None
    calculation: Expression | None = None
    next_line_id: str | None = None

    @field_validator('value')
    @classmethod
    def make_right_type(cls, v):
        if v is None:
            return v
        if isinstance(v, str):
            if v.lower().strip() == 'true':
                return True
            if v.lower().strip() == 'false':
                return False
            try:
                return int(v)
            except ValueError:
                pass
            try:
                return float(v)
            except ValueError:
                pass
            return v.strip('').strip('"')
        return v


class FlowControlElement(BaseModel):
    condition: Condition | None = None
    link: str | None = None


class FlowControl(BaseModel):
    if_block: FlowControlElement | None = None
    elif_blocks: list[FlowControlElement] = []
    else_block: FlowControlElement | None = None
    next_line_id: str | None = None


class Node(BaseModel):
    title: str | None = None
    checkpoint_name: str | None = None
    reaction: str | None = None
    wait: float | None = None
    time_for_status: float | None = None
    start_on_command: str | None = None
    flow: 'FlowList' = {}


class Script(BaseModel):
    settings: ScriptSettings
    start_node: str
    nodes: dict[str, Node] = {}


class ScriptInfo(BaseModel):
    start_node_name: str
    all_node_names: list[str]
    availble_paths: list[list[str]]


FlowType = Union[Message, Command, VariableCommand, FlowControl]
FlowList = dict[str, FlowType]
LineType = Union[
    Command,
    Message,
    VariableCommand,
    FlowControlElement,
    Option
]
status_message_command_types = [
    CommandType.typing,
    CommandType.upload_photo,
    CommandType.upload_video,
    CommandType.record_voice,
    CommandType.record_video_note
]
Expression
