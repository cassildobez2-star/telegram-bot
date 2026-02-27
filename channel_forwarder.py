from config import LOG_CHANNEL

async def forward_from_channel(bot, target_chat_id, message_id):
    await bot.copy_message(
        chat_id=target_chat_id,
        from_chat_id=LOG_CHANNEL,
        message_id=message_id
    )
