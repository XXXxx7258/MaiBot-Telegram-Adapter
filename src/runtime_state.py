from collections import OrderedDict
from typing import Optional


class TelegramRuntimeState:
    def __init__(self) -> None:
        self.bot_id: Optional[int] = None
        self._last_private_chat_id: Optional[int] = None
        self._message_chat_index: OrderedDict[int, int] = OrderedDict()
        self._message_chat_index_limit = 20000

    def set_bot_id(self, bot_id: Optional[int]) -> None:
        self.bot_id = bot_id

    def record_message(self, chat_id: int, message_id: int, chat_type: str) -> None:
        self._message_chat_index[message_id] = chat_id
        self._message_chat_index.move_to_end(message_id)
        while len(self._message_chat_index) > self._message_chat_index_limit:
            self._message_chat_index.popitem(last=False)

        if chat_type not in {"group", "supergroup"}:
            self._last_private_chat_id = chat_id

    def get_chat_id_by_message_id(self, message_id: int) -> Optional[int]:
        return self._message_chat_index.get(message_id)

    def get_last_private_chat_id(self) -> Optional[int]:
        return self._last_private_chat_id


telegram_runtime_state = TelegramRuntimeState()
