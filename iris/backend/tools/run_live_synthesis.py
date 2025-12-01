import json
from pathlib import Path
from app.agents.synthesis_agent import SynthesisAgent

SESSION_FILE = Path(__file__).parents[1] / 'backend' / 'app' / 'data' / 'sessions' / '7acc9c9b-5b15-4298-ae72-2b90883e2ea2.json'

if not SESSION_FILE.exists():
    print('Session file not found:', SESSION_FILE)
    raise SystemExit(1)

session = json.loads(SESSION_FILE.read_text(encoding='utf-8'))

# Choose a small set of papers to synthesize (the ones added most recently)
# For safety, we'll select 4 papers present in the session top-level 'papers'
selected = list(session.get('papers', {}).keys())[:4]
print('Selected papers for live synthesis:', selected)
analyses = [session['papers'][pid]['analysis'] for pid in selected if session['papers'][pid].get('analysis')]

agent = SynthesisAgent()
print('SynthesisAgent model:', type(agent.model), agent.model)

res = agent.synthesize(analyses)
print('\nSYNTHESIS RESULT:\n')
print(json.dumps(res, indent=2))
