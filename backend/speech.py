"""Connection-scoped PCM input, bounded utterances and cancellable responses."""
import asyncio
import contextlib
import io
import math
import sys
import wave
from array import array
from collections import deque
from uuid import uuid4
from . import inference

RATE = 16000

class SpeechSession:
    def __init__(self, send, dispatch):
        self.send, self.dispatch = send, dispatch
        self.stream = self.tid = self.turn = ''
        self.reply = None
        self.queue = asyncio.Queue(maxsize=1)
        self.worker = asyncio.create_task(self.recognize())
        self.reset()

    def reset(self):
        self.preroll = deque(maxlen=3)
        self.parts = []
        self.duration = self.silence = self.voiced = 0
        self.noise = .003

    def interrupt(self, turn):
        self.turn = turn
        if self.reply and not self.reply.done(): self.reply.cancel()
        while not self.queue.empty(): self.queue.get_nowait()

    async def respond(self, packet):
        turn = packet.get('turn') or str(uuid4())
        if turn != self.turn: self.interrupt(turn)
        async def emit(frame):
            if self.turn == turn:
                await self.send({'id': packet.get('id', ''), 'turn': turn, **frame})
        self.reply = asyncio.create_task(self.dispatch(packet, emit))
        try: return await self.reply
        except asyncio.CancelledError:
            if asyncio.current_task().cancelling(): raise
            return {'state': 'interrupted'}

    def feed(self, packet):
        if not self.stream or packet.get('stream') != self.stream: return
        data = packet.get('audio', b'')
        if not data or len(data) > 3200 or len(data) % 2:
            raise ValueError('Audioblöcke müssen PCM16 mit höchstens 100 ms enthalten.')
        turn = packet.get('turn', '')
        if not turn: raise ValueError('Der Sprachbeitrag fehlt.')
        if turn != self.turn:
            self.interrupt(turn)
            self.reset()
        self.rows = packet.get('rows', [])
        samples = array('h'); samples.frombytes(data)
        if sys.byteorder != 'little': samples.byteswap()
        rms = math.sqrt(sum(s*s for s in samples)/len(samples))/32768
        seconds = len(samples)/RATE
        voiced = rms > max(.014, min(.04, self.noise*3))
        if not self.parts:
            self.preroll.append(data)
            self.voiced = self.voiced + seconds if voiced else 0
            if not voiced: self.noise = .95*self.noise + .05*rms
            if self.voiced < .18: return
            self.parts = list(self.preroll)
            self.duration = sum(map(len, self.parts))/(2*RATE)
        else:
            self.parts.append(data)
            self.duration += seconds
        self.silence = 0 if voiced else self.silence + seconds
        if self.silence >= .65 or self.duration >= 15:
            if not self.queue.empty(): self.queue.get_nowait()
            self.queue.put_nowait((self.stream, self.turn, self.tid, b''.join(self.parts), self.rows))
            self.reset()

    async def recognize(self):
        while True:
            stream, turn, tid, pcm, rows = await self.queue.get()
            try:
                if stream != self.stream or turn != self.turn: continue
                await self.send({'op': 'voice.status', 'stream': stream, 'turn': turn, 'state': 'transcribing'})
                buf = io.BytesIO()
                with wave.open(buf, 'wb') as wav:
                    wav.setnchannels(1); wav.setsampwidth(2); wav.setframerate(RATE); wav.writeframes(pcm)
                text = await asyncio.to_thread(inference.transcribe, buf.getvalue())
                if stream != self.stream or turn != self.turn: continue
                if not text:
                    await self.send({'op': 'voice.status', 'stream': stream, 'turn': turn, 'state': 'listening'})
                    continue
                await self.respond({'id': str(uuid4()), 'op': 'message.send', 'tid': tid, 'text': text[:1000], 'turn': turn, 'rows': rows})
                if stream == self.stream and turn == self.turn:
                    await self.send({'op': 'voice.status', 'stream': stream, 'turn': turn, 'state': 'listening'})
            except asyncio.CancelledError: raise
            except Exception:
                import logging
                logging.getLogger('shopfloor').exception('Speech stream failed')
                await self.send({'op': 'voice.status', 'stream': stream, 'turn': turn, 'state': 'error', 'error': 'Der Sprachbeitrag konnte nicht verarbeitet werden.'})

    async def close(self):
        self.stream = ''
        self.interrupt(str(uuid4()))
        self.worker.cancel()
        with contextlib.suppress(asyncio.CancelledError): await self.worker
