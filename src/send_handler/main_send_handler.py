from typing import List

from maim_message import (
    UserInfo,
    GroupInfo,
    Seg,
    BaseMessageInfo,
    MessageBase,
)

from ..logger import logger
from ..runtime_state import telegram_runtime_state
from . import tg_sending


class SendHandler:
    def __init__(self):
        pass

    async def handle_message(self, raw_message_base_dict: dict) -> None:
        raw_message_base: MessageBase = MessageBase.from_dict(raw_message_base_dict)
        logger.info("接收到来自MaiBot的消息，处理中")
        return await self.send_normal_message(raw_message_base)

    async def send_normal_message(self, raw_message_base: MessageBase) -> None:
        if tg_sending.tg_message_sender is None:
            logger.error("Telegram 发送器未初始化")
            return

        message_info: BaseMessageInfo = raw_message_base.message_info
        message_segment: Seg = raw_message_base.message_segment
        group_info: GroupInfo | None = message_info.group_info
        user_info: UserInfo | None = message_info.user_info
        additional = getattr(message_info, "additional_config", None) or {}

        # 解析 reply 目标
        reply_to: int | None = self._extract_reply(message_segment, message_info)

        # 确定目标 chat_id
        chat_id: int | str | None
        if group_info and group_info.group_id:
            chat_id = group_info.group_id
            chat_id_source = "group_info.group_id"
        elif user_info and user_info.user_id:
            chat_id, chat_id_source = self._resolve_private_chat_id(user_info.user_id, reply_to, additional)
        else:
            logger.error("无法识别的消息类型（无目标 chat_id）")
            return

        logger.info(
            f"发送到Telegram: chat_id={chat_id} source={chat_id_source} "
            f"reply_to={reply_to} user_info.user_id={getattr(user_info, 'user_id', None)}"
        )

        # 扁平化 seglist 后按顺序发送（简单串行，避免复杂聚合）
        payloads = self._recursively_flatten(message_segment)
        if not payloads:
            logger.warning("消息段为空，不发送")
            return

        for seg in payloads:
            response: dict | None = None
            if seg.type == "text":
                response = await tg_sending.tg_message_sender.send_text(chat_id, seg.data, reply_to)
                reply_to = None  # 仅第一条携带回复
            elif seg.type == "image":
                response = await tg_sending.tg_message_sender.send_image_base64(chat_id, seg.data)
            elif seg.type == "imageurl":
                response = await tg_sending.tg_message_sender.send_image_url(chat_id, seg.data)
            elif seg.type == "voice":
                response = await tg_sending.tg_message_sender.send_voice_base64(chat_id, seg.data)
            elif seg.type == "videourl":
                response = await tg_sending.tg_message_sender.send_video_url(chat_id, seg.data)
            elif seg.type == "file":
                response = await tg_sending.tg_message_sender.send_document_url(chat_id, seg.data)
            elif seg.type == "emoji":
                response = await tg_sending.tg_message_sender.send_animation_base64(chat_id, seg.data)
            else:
                logger.debug(f"跳过不支持的发送类型: {seg.type}")
            self._log_send_result(seg.type, chat_id, response)

    def _recursively_flatten(self, seg_data: Seg) -> List[Seg]:
        items: List[Seg] = []
        if seg_data.type == "seglist":
            for s in seg_data.data:
                items.extend(self._recursively_flatten(s))
            return items
        items.append(seg_data)
        return items

    def _extract_reply(self, seg_data: Seg, message_info: BaseMessageInfo) -> int | None:
        # 优先读取 additional_config.reply_message_id，其次读取 Seg(reply)
        additional = getattr(message_info, "additional_config", None) or {}
        reply_id = additional.get("reply_message_id")
        if reply_id:
            try:
                return int(reply_id)
            except Exception:
                return None

        def _walk(seg: Seg) -> int | None:
            if seg.type == "seglist":
                for s in seg.data:
                    rid = _walk(s)
                    if rid:
                        return rid
                return None
            if seg.type == "reply":
                try:
                    return int(seg.data)
                except Exception:
                    return None
            return None

        return _walk(seg_data)

    def _resolve_private_chat_id(
        self, fallback_user_id: int | str, reply_to: int | None, additional: dict
    ) -> tuple[int | str, str]:
        chat_id_from_additional = additional.get("chat_id")
        if chat_id_from_additional is not None:
            return chat_id_from_additional, "additional_config.chat_id"

        fallback_user_id_int = self._to_int_or_none(fallback_user_id)
        bot_id = telegram_runtime_state.bot_id
        if fallback_user_id_int is not None and bot_id is not None and fallback_user_id_int == bot_id:
            if reply_to is not None:
                mapped_chat_id = telegram_runtime_state.get_chat_id_by_message_id(reply_to)
                if mapped_chat_id is not None:
                    return mapped_chat_id, "reply_to_mapping"

            last_private_chat_id = telegram_runtime_state.get_last_private_chat_id()
            if last_private_chat_id is not None:
                return last_private_chat_id, "last_private_chat_fallback"

        return fallback_user_id, "user_info.user_id"

    def _to_int_or_none(self, value: int | str | None) -> int | None:
        if value is None:
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    def _log_send_result(self, seg_type: str, chat_id: int | str | None, response: dict | None) -> None:
        if response is None:
            return
        if not response.get("ok"):
            logger.warning(f"Telegram发送失败: type={seg_type}, chat_id={chat_id}, response={response}")


send_handler = SendHandler()
