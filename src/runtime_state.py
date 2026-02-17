from collections import OrderedDict
from typing import Optional


class TelegramRuntimeState:
    _MESSAGE_CHAT_INDEX_LIMIT = 20000

    def __init__(self) -> None:
        self.bot_id: Optional[int] = None
        self._last_private_chat_id: Optional[int] = None
        self._message_chat_index: OrderedDict[tuple[int, int], None] = OrderedDict()

    def set_bot_id(self, bot_id: Optional[int]) -> None:
        self.bot_id = bot_id

    def record_message(self, chat_id: int, message_id: int, chat_type: str) -> None:
        message_key = (chat_id, message_id)
        self._message_chat_index[message_key] = None
        self._message_chat_index.move_to_end(message_key)
        if len(self._message_chat_index) > self._MESSAGE_CHAT_INDEX_LIMIT:
            self._message_chat_index.popitem(last=False)

        if chat_type == "private":
            self._last_private_chat_id = chat_id

    def get_chat_id_by_message_id(self, message_id: int) -> Optional[int]:
        for chat_id, current_message_id in reversed(self._message_chat_index.keys()):
            if current_message_id == message_id:
                return chat_id
        return None

    def get_last_private_chat_id(self) -> Optional[int]:
        return self._last_private_chat_id


telegram_runtime_state = TelegramRuntimeState()
