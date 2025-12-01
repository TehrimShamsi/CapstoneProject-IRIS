import os
import sys

# ensure package path
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from app.agents.analysis_agent import AnalysisAgent

os.environ['GOOGLE_API_KEY'] = os.environ.get('GOOGLE_API_KEY', '')
# Optionally set model
os.environ['GOOGLE_MODEL'] = os.environ.get('GOOGLE_MODEL', 'gemini-2.5-flash')

agent = AnalysisAgent()

text = "Our proposed transformer achieves 95.2% accuracy on dataset X. It outperforms baselines."

print('Calling _extract_with_gemini...')
res = agent._extract_with_gemini(text, chunk_id=0)
print('Result:', res)
