import os
import sys
import types

# ensure package path
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

# Inject a dummy vector_db module to avoid heavy dependencies like numpy/faiss
vec_mod = types.ModuleType('app.storage.vector_db')

def get_vector_db():
    class DummyDB:
        def add_paper_chunks(self, paper_id, chunks, paper_metadata=None):
            print(f"DummyDB.add_paper_chunks called: {len(chunks)} chunks")
        def save(self):
            print("DummyDB.save called")
    return DummyDB()

vec_mod.get_vector_db = get_vector_db
sys.modules['app.storage.vector_db'] = vec_mod

# Also ensure pdf processor exists
from app.agents.analysis_agent import AnalysisAgent

os.environ['GOOGLE_API_KEY'] = os.environ.get('GOOGLE_API_KEY', '')
os.environ['GOOGLE_MODEL'] = os.environ.get('GOOGLE_MODEL', 'gemini-2.5-flash')

agent = AnalysisAgent()

text = "Our proposed transformer achieves 95.2% accuracy on dataset X. It outperforms baselines."

print('Calling _extract_with_gemini...')
res = agent._extract_with_gemini(text, chunk_id=0)
print('Result:', res)
