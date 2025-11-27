"""List available Gemini models for the configured GOOGLE_API_KEY.

Run with the backend venv Python:
C:/.../.venv/Scripts/python.exe tools/list_models.py
"""
from google import genai
import os, json

print('GOOGLE_API_KEY present:', bool(os.environ.get('GOOGLE_API_KEY')))
try:
    client = genai.Client()
    models = client.models.list()
    # models may be a container with `.models` or iterable
    names = []
    if hasattr(models, 'models'):
        for m in models.models:
            names.append(getattr(m, 'name', str(m)))
    else:
        for m in models:
            names.append(getattr(m, 'name', str(m)))
    print('Found models (count={}):'.format(len(names)))
    print(json.dumps(names, indent=2))
except Exception as e:
    print('ERROR while listing models:', repr(e))
    # Try the alternate import path that some examples use
    try:
        from google import genai as genai2
        client2 = genai2.Client()
        models2 = client2.models.list()
        names2 = [getattr(m, 'name', str(m)) for m in getattr(models2, 'models', models2)]
        print('Found models via alternate import (count={}):'.format(len(names2)))
        print(json.dumps(names2, indent=2))
    except Exception as e2:
        print('Alternate attempt failed:', repr(e2))
