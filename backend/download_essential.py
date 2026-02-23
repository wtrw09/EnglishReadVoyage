from huggingface_hub import hf_hub_download
import os
import ssl

# SSL修复
ssl._create_default_https_context = ssl._create_unverified_context
os.environ['HF_ENDPOINT'] = 'https://hf-mirror.com'

print("Downloading essential model files...")
try:
    # 下载配置文件
    hf_hub_download(repo_id="hexgrad/Kokoro-82M", filename="config.json", local_dir=".")
    # 下载PyTorch模型
    hf_hub_download(repo_id="hexgrad/Kokoro-82M", filename="kokoro-v1_0.pth", local_dir=".")
    # 下载语音文件
    hf_hub_download(repo_id="hexgrad/Kokoro-82M", filename="voices/af_heart.pt", local_dir=".")
    print("Download successful!")
except Exception as e:
    print(f"Download failed: {e}")
