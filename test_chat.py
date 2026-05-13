"""
测试 engine.chat 是否正常
"""
import os, sys
os.chdir('D:/bk/DScode')
sys.path.insert(0, 'D:/bk/DScode')

from fix_proxy import apply as fix_proxy
fix_proxy()

from core.query_engine import QueryEngine
from tools.registry import create_registry

registry = create_registry()
engine = QueryEngine(tools_registry=registry, max_retries=1, retry_delay=0.5)

results = []

def cb(event_type, data):
    if event_type == 'text':
        results.append(data)
    elif event_type == 'tool_start':
        print(f'  🛠 Tool: {data.get("name")}')
    elif event_type == 'tool_end':
        print(f'  ✅ Tool done: {data.get("name")}')
    elif event_type == 'retry':
        print(f'  ⏳ {data.get("message", "")}')
    elif event_type == 'error':
        print(f'  ❌ Error: {data}')

print('Sending: 继续收复')
try:
    result = engine.chat('继续收复', callback=cb)
    print(f'Result length: {len(result) if result else 0}')
    print(f'First 200 chars: {result[:200] if result else "(empty)"}')
except Exception as e:
    import traceback
    traceback.print_exc()

print('Done!')
