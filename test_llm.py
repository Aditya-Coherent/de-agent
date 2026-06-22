import sys
sys.path.insert(0, 'src')
from me_engine.curve.config import AgentConfig
from me_engine.curve.llm import LLMClient

cfg = AgentConfig.load()
print('model:', cfg.model)
print('online:', cfg.is_online)

llm = LLMClient(cfg)
try:
    r = llm.complete_json('Respond only with valid JSON.', '{"test": true}')
    print('LLM response:', r)
except Exception as e:
    print('LLM error:', type(e).__name__, str(e)[:300])
