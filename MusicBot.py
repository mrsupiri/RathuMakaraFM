from Player import Song, MusicPlayer
from utils import *
from random import shuffle


class MusicBot(discord.Client):
    def __init__(self, BotConfig, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.voice_client = None
        self.volume = 100
        self.MusicPlayer = None
        self.now_playing_msg = None
        self.logger = start_logger()
        self.BotConfig = BotConfig

    async def get_voice_client(self, channel: discord.abc.GuildChannel):
        if isinstance(channel, discord.Object):
            channel = self.get_channel(channel.id)

        if not isinstance(channel, discord.VoiceChannel):
            self.logger.error(f"{channel.mention} is not voice channel")
            return

        return await channel.connect(timeout=60, reconnect=True)

    async def on_ready(self):
        self.logger.debug(f"Starting Bot as {self.user.name} ")
        self.loop.create_task(embed_for_nowplaying(self))
        self.loop.create_task(embed_for_queue(self))
        self.loop.create_task(update_song_progress(self))
        self.loop.create_task(save_status(self))

    async def on_connect(self):
        await self.auto_join()
        self.create_MusicPlayer()
        self.loop.create_task(chat_cleaner(self))
        self.loop.create_task(stream_logs('logs/RathuMakara.log', self))
        await asyncio.sleep(2)

    def create_MusicPlayer(self):
        queue = []
        if self.MusicPlayer:
            queue = self.MusicPlayer.queue
        self.MusicPlayer = MusicPlayer(self)
        self.MusicPlayer.bot_cmd_channel = self.get_channel(self.BotConfig.bot_cmd_channel)
        self.MusicPlayer.player_channel = self.get_channel(self.BotConfig.player_channel)
        self.MusicPlayer.song_request_channel = self.get_channel(self.BotConfig.song_request_channel)
        self.MusicPlayer.song_request_queue_channel = self.get_channel(self.BotConfig.song_request_queue_channel)
        self.MusicPlayer.playlist_queue_channel = self.get_channel(self.BotConfig.playlist_queue_channel)
        self.MusicPlayer.queue = queue

    async def join(self, channel):
        if self.voice_client and self.voice_client.is_connected():
            await self.voice_client.disconnect()
        self.voice_client = await self.get_voice_client(channel)
        self.MusicPlayer.voice = self.voice_client

    async def auto_join(self):
        await self.wait_until_ready()
        if self.voice_client and self.voice_client.is_connected():
            await self.voice_client.disconnect()
        self.voice_client = await self.get_voice_client(self.get_channel(self.BotConfig.bot_voice_channel))
        self.logger.debug(f"Auto Joining {self.get_channel(self.BotConfig.bot_voice_channel).mention}")

    async def on_reaction_add(self, reaction, user):
        if reaction.message.channel != self.MusicPlayer.song_request_queue_channel:
            return

        if not [y.id for y in user.roles if int(y.id) in self.BotConfig.bot_commanders]:
            self.logger.info(f"{user.name} is not authorized to accept song requests")
            return

        for request in self.MusicPlayer.request_queue:
            if reaction.message.id == request.user_request.id:
                if reaction.emoji == '✅':
                    await self.MusicPlayer.song_request_channel.send(
                        f"{request.requester.mention} Your song request was accepted :blush:"
                    )
                    self.logger.info(
                        f"{user.name} accepted {request.requester.name}'s Request to play {request.song_webpage_url}")
                    await self.cmd_play(request.song_webpage_url, author=request.requester, request=True, download=True)
                    self.MusicPlayer.request_queue.remove(request)
                    await reaction.message.delete()
                elif reaction.emoji == '❌':
                    await self.MusicPlayer.song_request_channel.send(
                        f"{request.requester.mention} Your song request was declined :sweat:"
                    )
                    self.logger.info(
                        f"{user.name} declined {request.requester.name}'s Request to play {request.song_webpage_url}")
                    self.MusicPlayer.request_queue.remove(request)
                    await reaction.message.delete()

    async def on_message(self, message):
        await self.wait_until_ready()

        if message.author == self.user:
            return

        message_content = message.content.strip()

        if not message_content.startswith(self.BotConfig.prefix):
            return

        if not self.BotConfig.bot_cmd_channel == self.get_channel(message.channel) and (
                message.channel != self.MusicPlayer.song_request_channel or not message_content.startswith('!req')):
            return

        if isinstance(message.channel, discord.abc.PrivateChannel):
            return

        cmd = message_content.strip(self.BotConfig.prefix).split(' ')[0].lower()
        args = ' '.join((message_content.strip(self.BotConfig.prefix).split(' ')[1:])).strip(" ")

        self.logger.info(f"{message.author.name} => !{cmd} {args}")
        if cmd == 'hello':
            await self.cmd_hello(message)

        elif cmd == 'play' or cmd == 'p':
            await self.cmd_play(args, download=True, author=message.author)

        elif cmd == 'playnow':
            await self.cmd_play(args, download=True, play_now=True, author=message.author)

        elif cmd == 'playnext' or cmd == 'pn':
            await self.cmd_play(args, download=True, play_next=True, author=message.author)

        elif cmd == 'playlist':
            await self.cmd_play(args, playlist=True, author=message.author)

        elif cmd == 'join':
            if message.author.voice:
                await self.join(message.author.voice.channel)
            else:
                await message.channel.send(
                    '{0.author.mention} You must be on voice channel to summon the bot'.format(message))

        elif cmd == 'volume' or cmd == 'v':
            await self.cmd_volume(args)

        elif cmd == 'skip' or cmd == 's':
            await self.cmd_skip()

        elif cmd == 'pause' or cmd == 'ps':
            await self.cmd_pause()

        elif cmd == 'resume' or cmd == 'r':
            await self.cmd_resume()

        elif cmd == 'clearqueue':
            await self.cmd_clear_queue()

        elif cmd == 'stream':
            await self.cmd_play(args, download=False, author=message.author)

        elif cmd == 'shuffle':
            shuffle(self.MusicPlayer.queue)
            await message.channel.send(':twisted_rightwards_arrows: Shuffling the queue pseudo randomly')

        elif cmd == 'remove' or cmd == 'rm':
            await self.cmd_remove_from_queue(args)

        elif cmd == 'move' or cmd == 'm':
            await self.cmd_move_song(args)

        elif cmd == 'request' or cmd == 'req':
            await self.cmd_request(args, message)

        elif cmd == 'autoplay' or cmd == 'ap':
            await self.cmd_autoplay(args)

        elif cmd == 'reset':
            await self.cmd_reset()

        elif cmd == 'leave' or cmd == 'fuckoff':

            self.logger.info("Bot is disconnecting")
            if self.voice_client and self.voice_client.is_connected():
                await self.voice_client.disconnect()
            await message.channel.send(':hand_splayed: :hand_splayed:')

        else:
            await message.channel.send(
                '{0.author.mention} !{1} is invalid command refer #bot-command-list for more info'.format(message, cmd))

    @staticmethod
    async def cmd_hello(message):
        await message.channel.send('Hello {0.author.mention}'.format(message))

    async def cmd_reset(self):
        await self.MusicPlayer.bot_cmd_channel.send(":arrows_counterclockwise: Restarting Bot")
        try:
            exit(1)
        except Exception as e:
            self.logger.error('Error While Restarting Screen')
            self.logger.exception(e)

    async def cmd_play(self, url, download=True, playlist=False, author=None, play_now=False, play_next=False,
                       request=False):
        if self.voice_client is None:
            await self.auto_join()

        if url.strip() == '' or not url:
            if not self.MusicPlayer.is_playing():
                await self.cmd_resume()
                return
            return False

        if not author:
            return False

        if 'www.podcasts.com' in url:
            song = await Song.podcast(url, author, self)
        elif play_now:
            song = await Song.stream(url, author, self)
        elif download and not playlist:
            song = await Song.download(url, author, self)
        elif playlist:
            song = await Song.download(url, author, self, playlist=playlist)
        elif not download:
            song = await Song.stream(url, author, self)
        else:
            song = await Song.download(url, author, self)

        if playlist:
            return True

        if request:
            song.user_request = True

        if song and not play_now and not play_next:
            await self.MusicPlayer.add(song)
            return True
        elif song and play_next:
            await self.MusicPlayer.add(song, play_now=True)
        elif song and play_now:
            await self.MusicPlayer.add(song, play_now=True)
            await self.cmd_skip()
            return True
        else:
            self.logger.warning(f"Can't play or find {url}")
            await self.MusicPlayer.bot_cmd_channel.send(
                "{} I couldn't find that song :disappointed_relieved:".format(author.mention))
            return False

    async def cmd_volume(self, volume, author=None):
        if not volume.isdigit():
            if not author:
                await self.MusicPlayer.bot_cmd_channel.send(":no_entry: Sound level is not given")
            else:
                await self.MusicPlayer.bot_cmd_channel.send(f"{author.mention} :no_entry: Sound level is not given")
            return False

        volume = int(volume)
        if self.MusicPlayer.volume * 100 > volume:
            for i in range(round(self.MusicPlayer.volume * 100), volume - 1, -1):
                self.MusicPlayer.set_volume(i)
                await asyncio.sleep(.01)
            if not author:
                await self.MusicPlayer.bot_cmd_channel.send(f":sound: Volume is set to {volume}")
            else:
                await self.MusicPlayer.bot_cmd_channel.send(
                    f":sound: Volume is set to {volume} by {author.name} from Web Dashboard")
            return True
        else:
            for i in range(round(self.MusicPlayer.volume * 100), volume + 1):
                self.MusicPlayer.set_volume(i)
                await asyncio.sleep(.01)
            if not author:
                await self.MusicPlayer.bot_cmd_channel.send(f":loud_sound: Volume is set to {volume}")
            else:
                await self.MusicPlayer.bot_cmd_channel.send(
                    f":loud_sound: Volume is set to {volume} by {author.name} from Web Dashboard")
            return True

    async def cmd_skip(self, author=None):
        if not self.MusicPlayer.current:
            await self.MusicPlayer.bot_cmd_channel.send("Can't Skip, Nothing is Playing")
            return False
        up_next = ""
        if self.MusicPlayer.queue:
            up_next = f"\n:play_pause: {self.MusicPlayer.queue[0].song_name} by {self.MusicPlayer.queue[0].song_uploader}"

        if not author:
            await self.MusicPlayer.bot_cmd_channel.send(
                f":track_next: Skipping {self.MusicPlayer.current.song_name}" + up_next)
        else:
            await self.MusicPlayer.bot_cmd_channel.send(
                f":track_next: Skipping {self.MusicPlayer.current.song_name} by {author.name} from Web Dashboard" + up_next)
        self.MusicPlayer.skip()
        return True

    async def cmd_pause(self, author=None):
        self.MusicPlayer.pause()
        if not author:
            await self.MusicPlayer.bot_cmd_channel.send(":pause_button: Paused")
        else:
            await self.MusicPlayer.bot_cmd_channel.send(f":pause_button: Paused by {author.name} from Web Dashboard")
        return True

    async def cmd_resume(self, author=None):
        if not author:
            await self.MusicPlayer.bot_cmd_channel.send(":arrow_forward: Resuming")
        else:
            await self.MusicPlayer.bot_cmd_channel.send(f":arrow_forward: Resuming by {author.name} from Web Dashboard")
        self.MusicPlayer.resume()
        return True

    async def cmd_clear_queue(self, author=None):
        self.logger.warning("Playlist was Cleared")
        self.MusicPlayer.clear()
        if not author:
            await self.MusicPlayer.bot_cmd_channel.send(":boom: Queue was Cleared")
        else:
            await self.MusicPlayer.bot_cmd_channel.send(f":boom: Queue was Cleared by {author.name} from Web Dashboard")

        return True

    async def cmd_remove_from_queue(self, index, author=None):
        if index.isdigit() and len(self.MusicPlayer.queue) >= int(index):
            index = int(index) - 1
            if not author:
                await self.MusicPlayer.bot_cmd_channel.send(
                    f":boom: {self.MusicPlayer.queue[index].song_name} was Removed")
            else:
                await self.MusicPlayer.bot_cmd_channel.send(
                    f":boom: {self.MusicPlayer.queue[index].song_name} was Removed by {author.name} from Web Dashboard")
            del self.MusicPlayer.queue[index]
            return True
        return False

    async def cmd_move_song(self, arg, author=None):
        if len(arg.split(" ")) == 2:
            current, new = arg.split(" ")
        else:
            current = arg
            new = None

        if current == new:
            return False
        if current.isdigit() and len(self.MusicPlayer.queue) >= int(current):
            current = int(current)
            if new and new.isdigit() and len(self.MusicPlayer.queue) >= int(new):
                new = int(new)
                song = self.MusicPlayer.queue.pop(current - 1)
                self.MusicPlayer.queue.insert(new - 1, song)
                if not author:
                    if current > new:
                        await self.MusicPlayer.bot_cmd_channel.send(
                            f":arrow_up_small:  {song.song_name} was Moved #{new}")
                    else:
                        await self.MusicPlayer.bot_cmd_channel.send(
                            f":arrow_down_small: {song.song_name} was Moved #{new}")
                else:
                    if current > new:
                        await self.MusicPlayer.bot_cmd_channel.send(
                            f":arrow_up_small:  {song.song_name} was Moved #{new} by {author.name} from Web Dashboard")
                    else:
                        await self.MusicPlayer.bot_cmd_channel.send(
                            f":arrow_down_small: {song.song_name} was Moved #{new} by {author.name} from Web Dashboard")

            else:
                song = self.MusicPlayer.queue.pop(current - 1)
                self.MusicPlayer.queue.insert(0, song)
                if not author:
                    await self.MusicPlayer.bot_cmd_channel.send(
                        f":arrow_double_up: {song.song_name} was Moved to the Top of the Queue")
                else:
                    await self.MusicPlayer.bot_cmd_channel.send(
                        f":arrow_double_up: {song.song_name} was Moved to the Top of the Queue by {author.name} from Web Dashboard")
            return True

    async def cmd_request(self, arg, message, author=None):
        if arg == '':
            return False
        if message:
            await Song.search(arg, message, self)
        elif author:
            await Song.search(arg, None, self, author=author)

    async def cmd_autoplay(self, arg, author=None):
        if arg == 'on':
            self.MusicPlayer.autoplay = True
            self.logger.info(f"AutoPlay was Enabled")
            if author:
                await self.MusicPlayer.bot_cmd_channel.send(
                    f"AutoPlay is Now Enabled by {author.name} from Web Dashboard")
            else:
                await self.MusicPlayer.bot_cmd_channel.send("AutoPlay is Now Enabled")
            return True

        elif arg == 'off':
            self.MusicPlayer.autoplay = False
            self.logger.info(f"AutoPlay was Disabled")
            if author:
                await self.MusicPlayer.bot_cmd_channel.send(
                    f"AutoPlay is Now Disabled by {author.name} from Web Dashboard")
            else:
                await self.MusicPlayer.bot_cmd_channel.send("AutoPlay is Now Disabled")
            return True
        else:
            return False



