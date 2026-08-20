import os
import sys
import threading
import queue
from typing import List, Optional, Iterator, Any

# Try to prefer local Hermes Agent integration (run_agent.AIAgent) when available
# (user provided D:\code\hermes-agent). If not available, fall back to deepagent
# adapter for environments that install a separate deepagent package.
try:
    import deepagent
except Exception:
    deepagent = None

from .config import get_settings, Settings
from .models import ShotSpec
from .planner import ShotPlanner


class Harness:
    """Harness that prefers Hermes Agent (local run_agent.AIAgent) and falls
    back to a generic deepagent adapter.

    Behavior:
    - If HERMES_AGENT_PATH env var or default path exists, we add it to sys.path
      and try to import run_agent.AIAgent. If successful, use that for chat and
      stream (preferred — uses Hermes' tooling and provider plumbing).
    - Otherwise, try to use deepagent library with a defensive adapter.
    """

    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or get_settings()
        self.model = (
            self.settings.llm_model_name
            or os.getenv("LLM_MODEL_NAME")
            or os.getenv("OPENAI_MODEL")
            or "gpt-3.5-turbo"
        )
        self.api_token = (
            self.settings.llm_api_token
            or os.getenv("LLM_API_TOKEN")
            or os.getenv("OPENAI_API_KEY")
        )
        self.planner = ShotPlanner(self.settings)

        self.hermes_agent = None
        self.client = None

        # Attempt to load local Hermes Agent (run_agent.AIAgent)
        hermes_path = os.getenv("HERMES_AGENT_PATH", r"D:\\code\\hermes-agent")
        try:
            if hermes_path and os.path.exists(hermes_path):
                if hermes_path not in sys.path:
                    sys.path.insert(0, hermes_path)
                try:
                    from run_agent import AIAgent

                    # Construct minimal AIAgent; pass API key and model where supported
                    try:
                        self.hermes_agent = AIAgent(api_key=self.api_token, model=self.model)
                    except Exception:
                        # best-effort: try without api_key
                        try:
                            self.hermes_agent = AIAgent(model=self.model)
                        except Exception:
                            self.hermes_agent = None
                except Exception:
                    self.hermes_agent = None
        except Exception:
            self.hermes_agent = None

        # If Hermes agent not available, fall back to deepagent adapter
        if self.hermes_agent is None:
            if deepagent is None:
                self.client = None
            else:
                self.client = None
                try:
                    Client = getattr(deepagent, "Client", None)
                    if Client:
                        self.client = Client(api_key=self.api_token) if self.api_token else Client()
                    elif hasattr(deepagent, "DeepAgent"):
                        self.client = (
                            deepagent.DeepAgent(api_key=self.api_token)
                            if self.api_token
                            else deepagent.DeepAgent()
                        )
                    else:
                        factory = getattr(deepagent, "create_client", None) or getattr(deepagent, "init", None)
                        if factory:
                            try:
                                self.client = factory(api_key=self.api_token) if self.api_token else factory()
                            except TypeError:
                                self.client = factory()
                        else:
                            self.client = deepagent
                except Exception:
                    self.client = None

    # ------------------ Hermes helpers ------------------
    def _ensure_hermes(self):
        if self.hermes_agent is None:
            raise RuntimeError(
                "Hermes Agent not available. Set HERMES_AGENT_PATH to a local hermes-agent checkout or install deepagent."
            )

    def _format_messages_for_hermes(self, messages: List[dict]) -> str:
        # Hermes expects a text prompt; convert role/message list to a single string
        parts = []
        for m in messages:
            role = m.get("role", "user")
            content = m.get("content", "")
            parts.append(f"[{role}] {content}")
        return "\n".join(parts)

    def chat_hermes(self, messages: List[dict]) -> dict:
        """Synchronous chat via Hermes AIAgent.chat. Returns {content: str}."""
        self._ensure_hermes()
        prompt = self._format_messages_for_hermes(messages)
        # AIAgent.chat(message: str, stream_callback: Optional[callable]=None)
        resp = self.hermes_agent.chat(prompt)
        # resp may be a string or object — normalize
        if isinstance(resp, str):
            return {"content": resp}
        if isinstance(resp, dict):
            return {"content": resp.get("content") or resp.get("message") or str(resp)}
        if hasattr(resp, "content"):
            return {"content": getattr(resp, "content")}
        return {"content": str(resp)}

    def chat_stream_hermes(self, messages: List[dict]) -> Iterator[str]:
        """Stream via Hermes AIAgent.chat using stream_callback.

        Uses a queue and a helper thread to bridge the callback-style stream into
        a Python generator that yields text chunks.
        """
        self._ensure_hermes()
        prompt = self._format_messages_for_hermes(messages)

        q: "queue.Queue[Optional[str]]" = queue.Queue()

        def stream_cb(delta: str):
            try:
                q.put(delta)
            except Exception:
                pass

        sentinel = object()

        def runner():
            try:
                # AIAgent.chat will invoke stream_cb repeatedly with deltas
                self.hermes_agent.chat(prompt, stream_callback=stream_cb)
            except Exception as e:
                q.put(f"[ERROR] {e}")
            finally:
                q.put(sentinel)

        t = threading.Thread(target=runner, daemon=True)
        t.start()

        while True:
            item = q.get()
            if item is sentinel:
                break
            yield item

    # ------------------ Deepagent fallback ------------------
    def _ensure_client(self):
        if deepagent is None:
            raise RuntimeError(
                "deepagent library is not installed. Install it (pip install deepagent) or make Hermes Agent available."
            )
        if self.client is None:
            raise RuntimeError(
                "deepagent client could not be constructed automatically. Check deepagent package API or provide correct configuration."
            )

    def chat_deepagent(self, messages: List[dict]) -> dict:
        self._ensure_client()
        resp = None
        try:
            if hasattr(self.client, "chat"):
                resp = self.client.chat(messages=messages, model=self.model)
            elif hasattr(self.client, "create_chat"):
                resp = self.client.create_chat(model=self.model, messages=messages)
            elif hasattr(self.client, "run"):
                resp = self.client.run({"model": self.model, "messages": messages})
            elif hasattr(deepagent, "chat"):
                resp = deepagent.chat(model=self.model, messages=messages)
            else:
                raise RuntimeError("deepagent client has no recognized chat method")
        except TypeError:
            if hasattr(self.client, "chat"):
                resp = self.client.chat(messages, self.model)

        if resp is None:
            raise RuntimeError("No response from deepagent chat call")

        if isinstance(resp, str):
            return {"content": resp}
        if isinstance(resp, dict):
            if "content" in resp:
                return {"content": resp["content"]}
            if "message" in resp:
                m = resp["message"]
                if isinstance(m, dict) and "content" in m:
                    return {"content": m["content"]}
                return {"content": str(m)}
            if "choices" in resp and isinstance(resp["choices"], list) and resp["choices"]:
                c0 = resp["choices"][0]
                if isinstance(c0, dict) and "message" in c0:
                    msg = c0["message"]
                    if isinstance(msg, dict) and "content" in msg:
                        return {"content": msg["content"]}
                if isinstance(c0, str):
                    return {"content": c0}
            return {"content": str(resp)}
        if hasattr(resp, "content"):
            return {"content": getattr(resp, "content")}
        return {"content": str(resp)}

    def chat_stream_deepagent(self, messages: List[dict]) -> Iterator[str]:
        self._ensure_client()
        streamer = None
        try:
            if hasattr(self.client, "stream_chat"):
                streamer = self.client.stream_chat(messages=messages, model=self.model)
            elif hasattr(self.client, "stream"):
                streamer = self.client.stream(model=self.model, messages=messages)
            elif hasattr(deepagent, "stream_chat"):
                streamer = deepagent.stream_chat(model=self.model, messages=messages)
        except Exception:
            streamer = None

        if streamer is None:
            resp = self.chat_deepagent(messages)
            yield resp.get("content", "")
            return

        try:
            for item in streamer:
                if isinstance(item, str):
                    yield item
                elif isinstance(item, dict):
                    if "delta" in item:
                        yield item["delta"].get("content", "") if isinstance(item["delta"], dict) else str(item["delta"])
                    elif "content" in item:
                        yield item["content"]
                    elif "text" in item:
                        yield item["text"]
                    else:
                        yield str(item)
                else:
                    yield str(item)
        except TypeError:
            resp = self.chat_deepagent(messages)
            yield resp.get("content", "")

    # ------------------ Public API ------------------
    def chat(self, messages: List[dict]) -> dict:
        if self.hermes_agent is not None:
            return self.chat_hermes(messages)
        return self.chat_deepagent(messages)

    def chat_stream(self, messages: List[dict]) -> Iterator[str]:
        if self.hermes_agent is not None:
            return self.chat_stream_hermes(messages)
        return self.chat_stream_deepagent(messages)

    def plan_shots(self, story_prompt: str, shot_count: Optional[int] = None) -> List[ShotSpec]:
        """Build an initial plan with the ShotPlanner and optionally refine prompts via the model.

        Returns a list of ShotSpec objects.
        """
        shot_count = shot_count or self.settings.default_shots
        base_shots = self.planner.build_plan(story_prompt, shot_count=shot_count)

        # Try to refine each shot prompt by asking the model to enhance cinematic details.
        refined = []
        for idx, shot in enumerate(base_shots):
            system = (
                "You are a helpful assistant that rewrites short scene descriptions into vivid, cinematic image "
                "prompts suitable for a video generation model. Keep them concise but descriptive, include camera motion, "
                "lighting, mood, and important visual details."
            )
            user = f"Rewrite this scene description into a cinematic prompt:\n\n{shot.prompt}"
            try:
                msg = self.chat([{"role": "system", "content": system}, {"role": "user", "content": user}])
                content = msg.get("content", "").strip()
                if content:
                    shot.prompt = content
            except Exception:
                # on any model error, fall back to planner's prompt
                pass
            refined.append(shot)

        return refined
