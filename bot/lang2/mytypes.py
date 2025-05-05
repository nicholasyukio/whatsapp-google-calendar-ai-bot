from typing import TypedDict, List, Literal, Union

UnknownStr = Literal["unknown"]
TheSameStr = Literal["the_same"]

class ChatMessage(TypedDict):
    role: Literal["system", "user", "assistant"]
    content: str

class ActionResult(TypedDict, total=False):
    success: bool
    info: str

# ----- Define BotState -----
class State(TypedDict):
    user_id: str
    username: str
    email: str
    conversation: str
    messages: List[ChatMessage]
    updated_at_utc: str

class EventNow(TypedDict):
    event_id: Union[str, UnknownStr]
    event_name: Union[str, UnknownStr]
    start_time: Union[str, UnknownStr]
    end_time: Union[str, UnknownStr]
    description: Union[str, UnknownStr]
    invited_people: List[str]
    location: Union[str, UnknownStr]

class EventLater(TypedDict):
    event_name: Union[str, TheSameStr, UnknownStr]
    start_time: Union[str, TheSameStr, UnknownStr]
    end_time: Union[str, TheSameStr, UnknownStr]
    description: Union[str, TheSameStr, UnknownStr]
    invited_people: List[Union[str, TheSameStr]]
    location: Union[str, TheSameStr, UnknownStr]

class UpdateData(TypedDict):
    now: EventNow
    later: EventLater

class CancelData(TypedDict, total=False):
    event_id: Union[str, UnknownStr]

class ScheduleData(TypedDict, total=False):
    event_name: Union[str, UnknownStr]
    start_time: Union[str, UnknownStr]
    end_time: Union[str, UnknownStr]
    description: Union[str, UnknownStr]
    invited_people: List[str]
    location: Union[str, UnknownStr]

class IntentData(TypedDict, total=False):
    kind: str
    data: Union[ScheduleData, CancelData, UpdateData]

class ExtractedData(TypedDict, total=False): 
    username: str
    email: str
    intents: List[IntentData]