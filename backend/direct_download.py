import requests
import os

files = [
    ("config.json", "https://hf-mirror.com/hexgrad/Kokoro-82M/resolve/main/config.json"),
    ("kokoro-v1_0.pth", "https://hf-mirror.com/hexgrad/Kokoro-82M/resolve/main/kokoro-v1_0.pth"),
    ("voices/af_heart.pt", "https://hf-mirror.com/hexgrad/Kokoro-82M/resolve/main/voices/af_heart.pt")
]

os.makedirs("voices", exist_ok=True)

print("Downloading via requests from mirror...")
for filename, url in files:
    print(f"Downloading {filename}...")
    try:
        r = requests.get(url, stream=True, verify=False)
        r.raise_for_status()
        with open(filename, 'wb') as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)
        print(f"Successfully downloaded {filename}")
    except Exception as e:
        print(f"Failed to download {filename}: {e}")
