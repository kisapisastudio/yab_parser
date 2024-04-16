from pydantic import BaseModel, model_validator
from pydantic_core import PydanticCustomError


class DefaultSettings(BaseModel):
    wait: float
    time_for_status: float
    reaction: str
    languages: dict[str, str]


class TechMessages(BaseModel):
    save_menu_text: dict[str, str]
    cancel_menu_text: dict[str, str]
    restart_text: dict[str, str]
    restart_button_text: dict[str, str]
    cancel_button_text: dict[str, str]


class ScriptSettings(BaseModel):
    reactions: dict[str, dict[str, list[str]]]
    tech_messages: TechMessages
    default_settings: DefaultSettings

    @model_validator(mode='after')
    def check_default_reaction(self) -> 'ScriptSettings':
        if self.default_settings.reaction not in self.reactions:
            raise PydanticCustomError(
                'ValueError',
                f'Default reaction "{self.default_settings.reaction}" not found in reactions',
            )
        return self

    @model_validator(mode='after')
    def check_languages(self) -> 'ScriptSettings':
        for lang in self.default_settings.languages:
            for reaction in self.reactions:
                if lang not in self.reactions[reaction]:
                    raise PydanticCustomError(
                        'ValueError',
                        f'Language "{lang}" not found in reaction "{reaction}"',
                    )
            _t_msg = self.tech_messages.model_dump()
            for message in _t_msg:
                if lang not in _t_msg[message]:
                    raise PydanticCustomError(
                        'ValueError',
                        f'Language "{lang}" not found in tech message "{message}"',
                    )
        return self
