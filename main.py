"""FakeDeafen-style resend sequence with no audio capture. No commands or audio capture."""
import asyncio
import ctypes.util
import os
import signal
import sys

import discord


class VoiceAccount(discord.Client):
    def __init__(self, channel_id):
        super().__init__()
        self.channel_id = channel_id
        self.join_lock = asyncio.Lock()
        self.failed = False

    async def on_ready(self):
        async with self.join_lock:
            if self.is_closed() or self.voice_clients:
                return
            print("Discord подключён; подключаю войс.", flush=True)
            try:
                channel = self.get_channel(self.channel_id)
                if channel is None:
                    channel = await self.fetch_channel(self.channel_id)
                if not isinstance(channel, discord.VoiceChannel):
                    raise ValueError("Expected an ordinary guild voice channel")
                await channel.connect(
                    self_mute=False,
                    self_deaf=False,
                    reconnect=True,
                    timeout=60,
                )
                # Match FakeDeafen.forceResend(): toggle mute on, then back off,
                # while its outgoing voiceStateUpdate patch forces deaf=True.
                await channel.guild.change_voice_state(
                    channel=channel, self_mute=True, self_deaf=True
                )
                await asyncio.sleep(0.06)
                await channel.guild.change_voice_state(
                    channel=channel, self_mute=False, self_deaf=True
                )
                print("FakeDeafen: последовательность отправлена; ожидаем флаги Discord.", flush=True)
            except Exception as error:
                # Do not print exception payloads, tokens or environment variables.
                print(f"Ошибка подключения: {type(error).__name__}", flush=True)
                self.failed = True
                await self.close()


    async def on_voice_state_update(self, member, before, after):
        if self.user is None or member.id != self.user.id:
            return
        if after.channel is None or after.channel.id != self.channel_id:
            return
        print(
            "Discord voice state: "
            f"self_mute={after.self_mute}, self_deaf={after.self_deaf}, "
            f"server_mute={after.mute}, server_deaf={after.deaf}",
            flush=True,
        )


async def run():
    token = os.environ.get("DISCORD_TOKEN", "").strip()
    channel_text = os.environ.get("VOICE_CHANNEL_ID", "").strip()
    if not token or not channel_text.isdecimal() or int(channel_text) <= 0:
        print("Задай DISCORD_TOKEN и числовой VOICE_CHANNEL_ID в Variables.", flush=True)
        return 1

    opus = ctypes.util.find_library("opus")
    if opus and not discord.opus.is_loaded():
        discord.opus.load_opus(opus)

    client = VoiceAccount(int(channel_text))
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(sig, lambda: asyncio.create_task(client.close()))
        except NotImplementedError:
            pass
    try:
        async with client:
            await client.start(token, reconnect=True)
    except Exception as error:
        print(f"Ошибка Discord: {type(error).__name__}", flush=True)
        return 1
    return 1 if client.failed else 0


if __name__ == "__main__":
    try:
        sys.exit(asyncio.run(run()))
    except KeyboardInterrupt:
        sys.exit(0)
