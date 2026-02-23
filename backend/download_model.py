from huggingface_hub import snapshot_download
import os

os.environ['HF_ENDPOINT'] = 'https://hf-mirror.com'
os.environ['HF_HUB_DISABLE_SYMLINKS'] = '1'

print("Downloading Kokoro model from mirror...")
try:
    # 这将把模型下载到默认的HF缓存中
    path = snapshot_download(repo_id="hexgrad/Kokoro-82M")
    print(f"Model downloaded to: {path}")
except Exception as e:
    print(f"Download failed: {e}")
