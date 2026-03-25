import httpx
import asyncio

async def test():
    url = 'https://api.minimaxi.com/v1/t2a_v2'
    headers = {
        'Authorization': 'Bearer sk-cp-dnnCMmPGHQwqbzqbPA8lVbDJClbU7GMxRqjd9kS6oXE1DiTjaNXGg01RwKr3ijuQgJFPvuutxieoGn9rIxIxFD5Njxe_knxNrA2x800tWwoPLNOjW-X-EPU',
        'Content-Type': 'application/json',
    }
    payload = {
        'model': 'speech-2.8-hd',
        'text': 'Hello, this is a test.',
        'stream': False,
        'voice_setting': {
            'voice_id': 'male-qn-qingse',
            'speed': 1.0,
            'vol': 1,
            'pitch': 0
        },
        'audio_setting': {
            'sample_rate': 32000,
            'bitrate': 128000,
            'format': 'mp3',
            'channel': 1
        }
    }
    
    print(f"Testing URL: {url}")
    print(f"Headers: {headers}")
    
    try:
        async with httpx.AsyncClient(timeout=30.0, verify=True) as client:
            print("Client created, making request...")
            response = await client.post(url, headers=headers, json=payload)
            print(f'Status: {response.status_code}')
            print(f'Response preview: {response.text[:200]}...')
    except Exception as e:
        print(f"Error: {type(e).__name__}: {e}")

asyncio.run(test())
