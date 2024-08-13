from pydantic import BaseModel, model_validator
from pydantic_core import PydanticCustomError


class DefaultSettings(BaseModel):
    wait: float
    time_for_status: float
    reaction: str
    native_language: str
    languages: dict[str, str]


class TechMessages(BaseModel):
    save_menu_text: str
    cancel_menu_text: str
    restart_text: str
    restart_button_text: str
    cancel_button_text: str


class ScriptSettings(BaseModel):
    reactions: dict[str, list[str]]
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
