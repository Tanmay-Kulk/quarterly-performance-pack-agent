"""LLM clients. ReplayClient reads saved outputs so the pipeline and its evaluation run offline and repeatably.
AnthropicClient shows the live integration (HTTPS call to the Messages API). Only public data may be sent: see README, AI Acceptable Use checklist."""
import json, os, urllib.request

class ReplayClient:
    def __init__(self, folder): self.folder = folder
    def complete(self, name):
        return open(os.path.join(self.folder, name), encoding="utf-8").read().strip()

class AnthropicClient:
    def __init__(self, api_key=None, model="claude-sonnet-5-5"):
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY"); self.model = model
        if not self.api_key: raise RuntimeError("set ANTHROPIC_API_KEY to use the live client")
    def complete(self, prompt):
        body = json.dumps({"model": self.model, "max_tokens": 400, "messages": [{"role": "user", "content": prompt}]}).encode()
        req = urllib.request.Request("https://api.anthropic.com/v1/messages", data=body, headers={"x-api-key": self.api_key, "anthropic-version": "2023-06-01", "content-type": "application/json"})
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.load(r)["content"][0]["text"].strip()
