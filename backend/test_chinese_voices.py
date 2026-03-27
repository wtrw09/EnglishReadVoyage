"""
测试各TTS服务的中文音色获取脚本
用于确定如何筛选中文音色
"""
import asyncio
import subprocess
import json
import os
import sqlite3
from pathlib import Path

# 数据库路径
DB_PATH = Path(__file__).parent / "data.db"


def get_api_keys_from_db():
    """从数据库获取用户配置的API Keys"""
    keys = {
        "minimax_api_key": None,
        "siliconflow_api_key": None,
        "doubao_app_id": None,
        "doubao_access_key": None,
    }
    
    if not DB_PATH.exists():
        print(f"数据库文件不存在: {DB_PATH}")
        return keys
    
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # 查询user_settings表
        cursor.execute("""
            SELECT minimax_api_key, siliconflow_api_key 
            FROM user_settings LIMIT 1
        """)
        row = cursor.fetchone()
        if row:
            keys["minimax_api_key"] = row[0]
            keys["siliconflow_api_key"] = row[1]
        
        conn.close()
    except Exception as e:
        print(f"读取数据库失败: {e}")
    
    return keys


def test_edge_tts_chinese():
    """测试Edge-TTS中文音色获取"""
    print("\n" + "="*60)
    print("1. Edge-TTS 中文音色测试")
    print("="*60)
    
    try:
        result = subprocess.run(
            ["edge-tts", "--list-voices"],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode != 0:
            print(f"edge-tts 执行失败: {result.stderr}")
            return []
        
        voices = []
        lines = result.stdout.strip().split('\n')
        
        for line in lines:
            if not line.strip() or 'Name' in line or '---' in line:
                continue
            
            parts = line.split()
            if not parts:
                continue
            
            voice_id = parts[0]
            
            # 筛选中文语音 (zh-CN, zh-HK, zh-TW)
            if voice_id.startswith('zh-CN') or voice_id.startswith('zh-HK') or voice_id.startswith('zh-TW'):
                # 提取性别
                gender = "Unknown"
                if "Female" in line:
                    gender = "Female"
                elif "Male" in line:
                    gender = "Male"
                
                # 提取语音名称
                voice_name = voice_id.split('-')[-1].replace('Neural', '').replace('Multilingual', '')
                
                # 地区映射
                region_map = {
                    'zh-CN': '中国大陆',
                    'zh-HK': '香港粤语',
                    'zh-TW': '台湾国语'
                }
                region_code = '-'.join(voice_id.split('-')[:2])
                region = region_map.get(region_code, region_code)
                
                voices.append({
                    "id": voice_id,
                    "name": f"{region} - {voice_name} ({gender})",
                    "region": region,
                    "gender": gender
                })
        
        print(f"找到 {len(voices)} 个中文音色:")
        for v in voices[:10]:  # 只显示前10个
            print(f"  - {v['id']}: {v['name']}")
        if len(voices) > 10:
            print(f"  ... 还有 {len(voices) - 10} 个音色")
        
        return voices
        
    except FileNotFoundError:
        print("edge-tts 未安装，请运行: pip install edge-tts")
        return []
    except Exception as e:
        print(f"获取Edge-TTS中文音色失败: {e}")
        return []


async def test_minimax_chinese(api_key):
    """测试MiniMax中文音色获取"""
    print("\n" + "="*60)
    print("2. MiniMax 中文音色测试")
    print("="*60)
    
    if not api_key:
        # 尝试从环境变量获取
        api_key = os.getenv("MINIMAX_API_KEY")
    
    if not api_key:
        print("未配置 MiniMax API Key")
        return []
    
    print(f"使用 API Key: {api_key[:10]}...")
    
    try:
        import httpx
        
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                "https://api.minimaxi.com/v1/get_voice",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                },
                json={"voice_type": "all"}
            )
            
            print(f"API响应状态: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                
                # 分析所有音色类型
                print("\n音色类型统计:")
                voice_types = data.keys()
                for vt in voice_types:
                    voices = data.get(vt)
                    if voices:
                        print(f"  - {vt}: {len(voices)} 个音色")
                    else:
                        print(f"  - {vt}: 0 个音色")
                
                # 先打印所有音色ID前缀统计
                all_prefixes = {}
                system_voices = data.get("system_voice")
                if not system_voices:
                    print("\n警告: system_voice 列表为空或None")
                    return []
                
                print(f"\nsystem_voice 类型: {type(system_voices)}")
                print(f"system_voice 长度: {len(system_voices)}")
                
                for voice in system_voices:
                    if not voice:
                        continue
                    voice_id = voice.get("voice_id", "")
                    if voice_id:
                        # 获取前缀 (如 English_, Chinese_ 等)
                        prefix = voice_id.split('_')[0] + '_' if '_' in voice_id else voice_id
                        all_prefixes[prefix] = all_prefixes.get(prefix, 0) + 1
                
                print("\n音色ID前缀统计:")
                for prefix, count in sorted(all_prefixes.items(), key=lambda x: -x[1]):
                    print(f"  - {prefix}: {count} 个")
                
                # 提取中文音色 (Chinese_ 开头，或包含 zh)
                chinese_voices = []
                
                for voice in system_voices:
                    voice_id = voice.get("voice_id", "")
                    voice_name = voice.get("voice_name", "")
                    description = voice.get("description", [])
                    desc_text = description[0] if description else ""
                    
                    # 筛选中文音色
                    # 1. Chinese (Mandarin)_ 前缀 - 标准普通话
                    # 2. Cantonese_ 前缀 - 粤语
                    # 3. male-qn-*, female-* 等中文风格名称
                    is_chinese = (
                        voice_id.startswith("Chinese (Mandarin)") or
                        voice_id.startswith("Cantonese_") or
                        voice_id.startswith("male-qn-") or
                        voice_id.startswith("female-") or
                        voice_id.startswith("chunzhen_") or
                        voice_id.startswith("lengdan_") or
                        voice_id.startswith("clever_") or
                        voice_id.startswith("cute_") or
                        voice_id.startswith("lovely_") or
                        voice_id.startswith("cartoon_") or
                        voice_id.startswith("bingjiao_") or
                        voice_id.startswith("junlang_") or
                        voice_id.startswith("badao_") or
                        voice_id.startswith("tianxin_") or
                        voice_id.startswith("qiaopi_") or
                        voice_id.startswith("wumei_") or
                        voice_id.startswith("diadia_") or
                        voice_id.startswith("danya_")
                    )
                    if is_chinese:
                        chinese_voices.append({
                            "id": voice_id,
                            "name": voice_name,
                            "description": desc_text,
                            "type": "system_voice"
                        })
                
                print(f"\n找到 {len(chinese_voices)} 个中文音色:")
                for v in chinese_voices[:10]:
                    print(f"  - {v['id']}: {v['name']} ({v['type']})")
                    if v.get('description'):
                        print(f"    描述: {v['description'][:50]}")
                
                if len(chinese_voices) > 10:
                    print(f"  ... 还有 {len(chinese_voices) - 10} 个音色")
                
                return chinese_voices
            else:
                print(f"API调用失败: {response.text[:200]}")
                return []
                
    except ImportError:
        print("httpx 未安装")
        return []
    except Exception as e:
        print(f"获取MiniMax中文音色失败: {e}")
        return []


async def test_siliconflow_chinese(api_key):
    """测试硅基流动中文音色获取"""
    print("\n" + "="*60)
    print("3. 硅基流动 中文音色测试")
    print("="*60)
    
    # 硅基流动目前没有公开的音色列表API，使用硬编码列表
    # 参考：https://docs.siliconflow.cn/cn/api/audio/speech
    
    print("硅基流动没有公开的音色列表API")
    print("根据文档，支持的中文音色可能包括：")
    
    # 根据硅基流动文档，CosyVoice2模型支持中文
    chinese_models = [
        {"id": "FunAudioLLM/CosyVoice2-0.5B", "name": "CosyVoice2 0.5B", "support_zh": True},
        {"id": "fnlp/MOSS-TTSD-v0.5", "name": "MOSS TTSD v0.5", "support_zh": False},
    ]
    
    print("\n支持中文的模型:")
    for m in chinese_models:
        if m['support_zh']:
            print(f"  - {m['id']}: {m['name']}")
    
    return []


async def test_doubao_chinese():
    """测试豆包TTS中文音色获取"""
    print("\n" + "="*60)
    print("4. 豆包 TTS 中文音色测试")
    print("="*60)
    
    # 豆包TTS的音色是硬编码的，参考现有代码
    # 从 Home.vue 中提取的中文音色列表
    
    doubao_zh_voices = [
        {"id": "zh_female_yingyujiaoyu_mars_bigtts", "name": "中文女声 - 教育风格"},
        {"id": "zh_male_chunhou_mars_bigtts", "name": "中文男声 - 淳厚"},
        {"id": "zh_female_shuangkuaisisi_moon_bigtts", "name": "中文女声 - 爽快思思"},
        {"id": "zh_male_chunhoudanao_mars_bigtts", "name": "中文男声 - 淳厚大脑"},
    ]
    
    print("豆包TTS中文音色（根据现有代码整理）:")
    for v in doubao_zh_voices:
        print(f"  - {v['id']}: {v['name']}")
    
    print("\n注：豆包TTS需要在火山引擎控制台查看完整音色列表")
    print("文档：https://www.volcengine.com/docs/6561/79823")
    
    return doubao_zh_voices


async def test_kokoro_chinese():
    """测试Kokoro TTS中文音色获取"""
    print("\n" + "="*60)
    print("5. Kokoro TTS 中文音色测试")
    print("="*60)
    
    try:
        import httpx
        
        # Kokoro API地址
        api_url = "http://localhost:8880/v1/audio/voices"
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(api_url)
            
            if response.status_code == 200:
                data = response.json()
                
                if isinstance(data, list):
                    all_voices = data
                elif isinstance(data, dict) and "voices" in data:
                    all_voices = data["voices"]
                else:
                    all_voices = []
                
                # 筛选中文音色 (通常以 zf_ 或 zm_ 开头)
                chinese_voices = [v for v in all_voices if v.startswith('z') and ('f_' in v or 'm_' in v)]
                
                print(f"总共 {len(all_voices)} 个音色")
                print(f"中文音色 {len(chinese_voices)} 个:")
                for v in chinese_voices[:10]:
                    print(f"  - {v}")
                
                return chinese_voices
            else:
                print(f"Kokoro服务未启动或不可用 (状态: {response.status_code})")
                return []
                
    except Exception as e:
        print(f"Kokoro服务连接失败: {e}")
        print("Kokoro TTS需要本地Docker服务运行")
        return []


async def main():
    """主测试函数"""
    print("="*60)
    print("TTS服务中文音色获取测试")
    print("="*60)
    
    # 从数据库获取API Keys
    keys = get_api_keys_from_db()
    print(f"\n从数据库获取的API Keys:")
    print(f"  - MiniMax API Key: {'已配置' if keys['minimax_api_key'] else '未配置'}")
    print(f"  - SiliconFlow API Key: {'已配置' if keys['siliconflow_api_key'] else '未配置'}")
    
    results = {}
    
    # 测试各服务
    results['edge-tts'] = test_edge_tts_chinese()
    results['minimax-tts'] = await test_minimax_chinese(keys['minimax_api_key'])
    results['siliconflow-tts'] = await test_siliconflow_chinese(keys['siliconflow_api_key'])
    results['doubao-tts'] = await test_doubao_chinese()
    results['kokoro-tts'] = await test_kokoro_chinese()
    
    # 总结
    print("\n" + "="*60)
    print("总结：各服务中文音色筛选规则")
    print("="*60)
    
    if results['edge-tts']:
        print("\n1. Edge-TTS 筛选规则:")
        print("   - 前缀匹配: zh-CN, zh-HK, zh-TW")
        print(f"   - 可用中文音色数量: {len(results['edge-tts'])}")
    
    if results['minimax-tts']:
        print("\n2. MiniMax 筛选规则:")
        print("   - 前缀匹配: Chinese_")
        print(f"   - 可用中文音色数量: {len(results['minimax-tts'])}")
    
    print("\n3. 硅基流动 筛选规则:")
    print("   - 使用 CosyVoice2 模型支持中文")
    print("   - 音色需要查看官方文档")
    
    print("\n4. 豆包 TTS 筛选规则:")
    print("   - 前缀匹配: zh_")
    print(f"   - 已知中文音色数量: {len(results['doubao-tts'])}")
    
    if results['kokoro-tts']:
        print("\n5. Kokoro TTS 筛选规则:")
        print("   - 前缀匹配: zf_ (女声), zm_ (男声)")
        print(f"   - 可用中文音色数量: {len(results['kokoro-tts'])}")


if __name__ == "__main__":
    asyncio.run(main())
