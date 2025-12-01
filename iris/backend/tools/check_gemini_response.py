import os
import json
import google.generativeai as genai

def print_attr(obj, name):
    try:
        val = getattr(obj, name)
        print(f"{name}: {repr(val)}")
    except Exception as e:
        print(f"{name}: <error reading: {e}>")

def main():
    key = os.getenv("GOOGLE_API_KEY")
    if not key:
        print("ERROR: GOOGLE_API_KEY not set in environment")
        return
    
    model_name = os.getenv("GOOGLE_MODEL", "gemini-2.5-flash")
    genai.configure(api_key=key)

    print("Using model:", model_name)
    model = genai.GenerativeModel(model_name)

    prompt = 'Return exactly this JSON object and nothing else: {"ok": true, "model_echo":"' + model_name + '"}'

    print("Calling model.generate_content with a tiny prompt to isolate behavior...")
    try:
        response = model.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(
                temperature=0.0,
                max_output_tokens=64
            )
        )
    except Exception as e:
        print("generate_content raised:", e)
        return

    print("--- response repr ---")
    try:
        print(repr(response))
    except Exception:
        print("<unable to repr response>")

    print("--- dir(response) ---")
    try:
        print(dir(response))
    except Exception:
        pass

    # Print likely useful attributes if present
    for name in ["text", "candidates", "parts", "result", "_result", "_error", "prompt_feedback"]:
        print_attr(response, name)

    # If candidates present, print their reprs
    try:
        cands = getattr(response, "candidates", None)
        if cands:
            print("--- candidates details ---")
            for i, c in enumerate(cands):
                print(f"candidate[{i}]: type={type(c)} repr={repr(c)[:400]}")
                # try to print nested attributes
                for a in ["content", "text", "message", "author"]:
                    if hasattr(c, a):
                        try:
                            print(f"  {a}: {getattr(c,a)!r}")
                        except Exception:
                            pass
    except Exception:
        pass

    # If parts present, print their reprs
    try:
        parts = getattr(response, "parts", None) or getattr(getattr(response, 'result', None), 'parts', None)
        if parts:
            print("--- parts details ---")
            for i, p in enumerate(parts):
                print(f"part[{i}]: type={type(p)} repr={repr(p)[:400]}")
                if hasattr(p, 'text'):
                    try:
                        print(f"  text: {getattr(p,'text')!r}")
                    except Exception:
                        pass
    except Exception:
        pass

    # Try to coerce to text
    try:
        txt = getattr(response, 'text', None)
        if not txt:
            # fallback to str(response)
            txt = str(response)
        print("--- final extracted text (first 1000 chars) ---")
        print(txt[:1000])
        # attempt to parse json if it looks like JSON
        s = txt.strip()
        if s.startswith('{') or s.startswith('['):
            try:
                parsed = json.loads(s)
                print("--- parsed JSON ---")
                print(json.dumps(parsed, indent=2))
            except Exception as e:
                print("JSON parse failed:", e)
    except Exception as e:
        print("error extracting text:", e)

if __name__ == '__main__':
    main()
