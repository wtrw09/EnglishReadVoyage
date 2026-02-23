from huggingface_hub import HfApi
import os
import ssl

ssl._create_default_https_context = ssl._create_unverified_context
os.environ['HF_ENDPOINT'] = 'https://hf-mirror.com'

api = HfApi()
try:
    files = api.list_repo_files(repo_id="hexgrad/Kokoro-82M")
    print("Files in repo:")
    for f in files:
        print(f)
except Exception as e:
    print(f"Failed to list files: {e}")
