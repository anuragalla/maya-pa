"""VoiceSession — manages a single Gemini Live session for one user.

Handles:
- Connecting to Gemini Live API with system prompt + tools
- Injecting user context as initial message
- Relaying audio between a WebSocket client and Gemini
- Dispatching tool calls to voice tool handlers
- State tracking (idle, listening, thinking, speaking)
"""

import asyncio
import base64
import json
import logging
from typing import Any, Literal

from google.genai import types

from live150.agent.genai_client import get_genai_client
from live150.db.session import async_session_factory
from live150.voice.context import build_system_prompt, build_user_context
from live150.voice.tools import TOOL_HANDLERS, get_tool_config

logger = logging.getLogger(__name__)

VOICE_MODEL = "gemini-2.5-flash-native-audio-preview-12-2025"

State = Literal["idle", "listening", "thinking", "speaking"]


class VoiceSession:
    def __init__(
        self,
        user_phone: str,
        access_token: str,
        api_base: str,
    ):
        self.user_phone = user_phone
        self.access_token = access_token
        self.api_base = api_base
        self.state: State = "idle"
        self.is_connected: bool = False
        self._gemini_session: Any = None
        self._gemini_ctx: Any = None
        self._tasks: list[asyncio.Task] = []

    async def connect(
        self,
        display_name: str,
        age: int | None,
        goals: list[str],
        conditions: list[str],
        timezone_name: str,
        memories: list[str],
    ) -> None:
        system_prompt = build_system_prompt()
        user_context = build_user_context(
            display_name=display_name,
            age=age,
            goals=goals,
            conditions=conditions,
            timezone_name=timezone_name,
            memories=memories,
        )

        client = get_genai_client()
        config = types.LiveConnectConfig(
            system_instruction=system_prompt,
            tools=get_tool_config(),
            response_modalities=["AUDIO"],
            temperature=1.0,
            enable_affective_dialog=True,
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="Aoede"),
                ),
            ),
        )

        self._gemini_ctx = client.aio.live.connect(model=VOICE_MODEL, config=config)
        self._gemini_session = await self._gemini_ctx.__aenter__()
        self.is_connected = True
        self.state = "listening"

        await self._gemini_session.send_client_content(
            turns=types.Content(
                role="user",
                parts=[types.Part(text=user_context)],
            ),
            turn_complete=True,
        )

    async def relay(self, websocket: Any) -> None:
        inbound = asyncio.create_task(self._inbound_loop(websocket), name="voice_inbound")
        outbound = asyncio.create_task(self._outbound_loop(websocket), name="voice_outbound")
        self._tasks = [inbound, outbound]

        try:
            done, pending = await asyncio.wait(
                self._tasks, return_when=asyncio.FIRST_EXCEPTION,
            )
            for task in pending:
                task.cancel()
            for task in done:
                if task.exception():
                    raise task.exception()
        except asyncio.CancelledError:
            pass

    async def _inbound_loop(self, websocket: Any) -> None:
        try:
            async for raw in websocket.iter_text():
                msg = json.loads(raw)
                if msg.get("type") == "audio":
                    pcm_bytes = base64.b64decode(msg["data"])
                    await self._gemini_session.send_realtime_input(
                        audio=types.Blob(data=pcm_bytes, mime_type="audio/pcm;rate=16000"),
                    )
        except Exception as e:
            logger.info("voice_inbound_closed", extra={"reason": str(e)})

    async def _outbound_loop(self, websocket: Any) -> None:
        try:
            async for msg in self._gemini_session.receive():
                if msg.server_content and msg.server_content.parts:
                    for part in msg.server_content.parts:
                        if part.inline_data and part.inline_data.data:
                            self.state = "speaking"
                            await websocket.send_json({
                                "type": "audio",
                                "data": base64.b64encode(part.inline_data.data).decode(),
                            })

                    if msg.server_content.turn_complete:
                        self.state = "listening"
                        await websocket.send_json({"type": "state", "state": "listening"})

                if msg.tool_call and msg.tool_call.function_calls:
                    self.state = "thinking"
                    await websocket.send_json({"type": "state", "state": "thinking"})
                    responses = await self._execute_tools(msg.tool_call.function_calls)
                    await self._gemini_session.send_tool_response(function_responses=responses)

        except Exception as e:
            logger.info("voice_outbound_closed", extra={"reason": str(e)})

    async def _execute_tools(self, function_calls: list) -> list:
        results = []
        async with async_session_factory() as db:
            for fc in function_calls:
                handler = TOOL_HANDLERS.get(fc.name)
                if not handler:
                    results.append(types.FunctionResponse(
                        name=fc.name, id=fc.id,
                        response={"error": f"Unknown tool: {fc.name}"},
                    ))
                    continue

                try:
                    result = await handler(
                        fc.args or {}, self.user_phone, db,
                        api_base=self.api_base, access_token=self.access_token,
                    )
                except Exception as e:
                    logger.warning("voice_tool_failed", extra={"tool": fc.name, "error": str(e)})
                    result = {"error": True, "message": str(e)}

                results.append(types.FunctionResponse(
                    name=fc.name, id=fc.id, response=result,
                ))
        return results

    async def close(self) -> None:
        for task in self._tasks:
            task.cancel()
        if self._gemini_session:
            try:
                await self._gemini_ctx.__aexit__(None, None, None)
            except Exception:
                pass
        self.is_connected = False
        self.state = "idle"
