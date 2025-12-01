import os
import sys

try:
    import google.generativeai as genai
except Exception as e:
    print("Failed to import google.generativeai:", e)
    sys.exit(1)

api_key = os.environ.get('GOOGLE_API_KEY')
if not api_key:
    print('GOOGLE_API_KEY not set in environment')
    sys.exit(1)

genai.configure(api_key=api_key)
model_name = os.environ.get('GOOGLE_MODEL', 'gemini-2.5-flash')
print('Using model:', model_name)

model = genai.GenerativeModel(model_name)

prompt = """Extract ONE key research claim from the following text. Return ONLY valid JSON and wrap it in explicit <JSON>...</JSON> tags (no extra explanation).

Text (truncated):
This is a short test text: Our proposed transformer achieves 95.2% accuracy on dataset X.

Required JSON structure (example):
<JSON>
{
  "text": "string - the claim as one clear sentence",
  "confidence": 0.0,
  "methods": ["method1", "method2"],
  "metrics": ["accuracy", "f1"]
}
</JSON>

Output MUST be exactly one <JSON>...</JSON> block containing valid JSON and nothing else.
"""

try:
    response = model.generate_content(
        prompt,
        generation_config=genai.types.GenerationConfig(temperature=0.15, max_output_tokens=280)
    )
    print('\n--- MODEL RESPONSE INSPECTION ---')
    try:
        print('REPR:', repr(response))
    except Exception as e:
        print('REPR error:', e)
    try:
        print('TYPE:', type(response))
    except Exception as e:
        print('TYPE error:', e)
    try:
        print('DIR:', dir(response))
    except Exception as e:
        print('DIR error:', e)
    try:
        print('TEXT attr:', getattr(response, 'text', None))
    except Exception as e:
        print('TEXT attr error:', e)

    try:
        if hasattr(response, 'result') and getattr(response.result, 'parts', None):
            parts = []
            for p in response.result.parts:
                parts.append(getattr(p, 'text', repr(p)))
            print('result.parts:', parts)
    except Exception as e:
        print('result.parts error:', e)

    try:
        if getattr(response, 'candidates', None):
            cands = []
            for cand in response.candidates:
                content = getattr(cand, 'content', {})
                parts = getattr(content, 'parts', None) or (content.get('parts') if isinstance(content, dict) else None)
                if parts:
                    cands.append([getattr(p, 'text', repr(p)) for p in parts])
                else:
                    cands.append(repr(cand))
            print('candidates:', cands)
    except Exception as e:
        print('candidates error:', e)

except Exception as e:
    print('Error calling model.generate_content:', e)
