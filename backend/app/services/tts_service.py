"""TTS服务用于文本转语音操作"""
import base64
import os
import hashlib
import httpx
import asyncio
import json
from typing import Optional, List, Set

from app.core.config import get_settings
from app.schemas.tts import TTSResponse


class TTSService:
    """TTS相关业务逻辑的服务层"""

    def __init__(self):
        """使用配置初始化服务"""
        self.settings = get_settings()

    async def generate_speech(
        self,
        text: str,
        voice: Optional[str] = None,
        api_url: Optional[str] = None,
        service_name: Optional[str] = None,
        doubao_app_id: Optional[str] = None,
        doubao_access_key: Optional[str] = None,
        doubao_resource_id: Optional[str] = None,
        speed: Optional[float] = None
    ) -> TTSResponse:
        """
        使用TTS API从文本生成语音

        参数:
            text: 要转换为语音的文本
            voice: 语音ID（默认为配置的默认语音）
            api_url: 自定义TTS服务地址，为空则使用系统默认
            service_name: 服务名称 'kokoro-tts' 或 'doubao-tts'
            doubao_app_id: 豆包APP ID
            doubao_access_key: 豆包Access Key
            doubao_resource_id: 豆包Resource ID
            speed: 朗读速度 (0.5-2.0)

        返回:
            包含音频URL的TTSResponse

        异常:
            Exception: 如果TTS API调用失败
        """
        # 确定使用哪个服务
        if service_name == "doubao-tts":
            return await self.generate_doubao_speech(
                text=text,
                voice=voice,
                app_id=doubao_app_id,
                access_key=doubao_access_key,
                resource_id=doubao_resource_id,
                speed=speed
            )

        # 默认使用Kokoro
        if voice is None:
            voice = self.settings.KOKORO_DEFAULT_VOICE

        # 使用自定义API URL或系统默认
        tts_api_url = api_url if api_url else self.settings.KOKORO_API_URL

        # 调用Kokoro Docker API
        print(f"调用TTS API: {tts_api_url}, voice={voice}, speed={speed}, text={text[:50]}...")
        async with httpx.AsyncClient(timeout=self.settings.TTS_TIMEOUT) as client:
            payload = {
                "model": "kokoro",
                "input": text,
                "voice": voice,
                "response_format": "mp3",
                "speed": speed if speed is not None else 1.0
            }
            print(f"TTS请求payload: {payload}")
            response = await client.post(tts_api_url, json=payload)
            print(f"TTS API响应: status={response.status_code}")

            if response.status_code != 200:
                print(f"TTS API错误: {response.text}")
                raise Exception(
                    f"TTS API returned {response.status_code}: {response.text}"
                )

            # 检查响应内容是否为空
            if not response.content or len(response.content) == 0:
                print(f"TTS API返回空内容: status={response.status_code}")
                raise Exception("未收到音频数据")

            # 返回音频数据（base64编码）
            audio_base64 = base64.b64encode(response.content).decode('utf-8')
            print(f"TTS音频生成成功, 大小: {len(response.content)} bytes")

        return TTSResponse(audio_data=audio_base64)

    async def generate_doubao_speech(
        self,
        text: str,
        voice: Optional[str] = None,
        app_id: Optional[str] = None,
        access_key: Optional[str] = None,
        resource_id: Optional[str] = None,
        speed: Optional[float] = None
    ) -> TTSResponse:
        """
        使用豆包TTS API从文本生成语音

        参数:
            text: 要转换为语音的文本
            voice: 语音ID
            app_id: 豆包APP ID
            access_key: 豆包Access Key
            resource_id: 豆包Resource ID
            speed: 朗读速度 (0.5-2.0)

        返回:
            包含音频URL的TTSResponse

        异常:
            Exception: 如果TTS API调用失败
        """
        # 使用默认值
        if voice is None:
            voice = self.settings.DOUBAO_DEFAULT_VOICE
        if resource_id is None:
            resource_id = self.settings.DOUBAO_DEFAULT_RESOURCE_ID
        if speed is None:
            speed = 1.0
        if not app_id or not access_key:
            raise Exception("豆包TTS需要配置app_id和access_key")

        # 调用豆包TTS API
        url = self.settings.DOUBAO_API_URL
        headers = {
            "X-Api-App-Id": app_id,
            "X-Api-Access-Key": access_key,
            "X-Api-Resource-Id": resource_id,
            "Content-Type": "application/json",
            "Connection": "keep-alive",
        }

        # 构建请求体，添加速度参数
        audio_params = {
            "format": "mp3",
            "sample_rate": 24000,
            "enable_timestamp": True
        }
        # 豆包TTS速度参数: speech_rate, 范围[-50, 100]
        # 100=2.0倍速, 0=1.0倍速, -50=0.5倍速
        if speed != 1.0:
            # 将 0.25-4.0 映射到 -50-100
            # speed 0.5 -> speech_rate -50
            # speed 1.0 -> speech_rate 0
            # speed 2.0 -> speech_rate 100
            speech_rate = int((speed - 1.0) * 100)
            audio_params["speech_rate"] = max(-50, min(100, speech_rate))

        payload = {
            "user": {"uid": "default_user"},
            "req_params": {
                "text": text,
                "speaker": voice,
                "audio_params": audio_params,
                "additions": json.dumps({
                    "explicit_language": "zh",
                    "disable_markdown_filter": True
                })
            }
        }

        print(f"调用豆包TTS API: {url}, voice={voice}, resource_id={resource_id}, speed={speed}")
        print(f"  text={text[:50]}...")

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                # 使用 stream 方法进行流式请求
                async with client.stream("POST", url, headers=headers, json=payload) as response:
                    if response.status_code != 200:
                        error_text = await response.aread()
                        print(f"豆包TTS API错误: {response.status_code}, {error_text}")
                        raise Exception(f"豆包TTS API returned {response.status_code}: {error_text}")

                    # 流式读取音频数据
                    audio_data = bytearray()
                    async for line in response.aiter_lines():
                        if not line:
                            continue
                        try:
                            data = json.loads(line)
                            # 检查是否有音频数据
                            if data.get("code", 0) == 0 and "data" in data and data["data"]:
                                chunk_audio = base64.b64decode(data["data"])
                                audio_data.extend(chunk_audio)
                            # 检查是否完成
                            elif data.get("code", 0) == 20000000:
                                break
                            # 检查错误
                            elif data.get("code", 0) > 0:
                                print(f"豆包TTS错误: {data}")
                                break
                        except json.JSONDecodeError:
                            continue

                    if audio_data:
                        # 返回音频数据（base64编码）
                        audio_base64 = base64.b64encode(audio_data).decode('utf-8')
                        print(f"豆包TTS生成成功, 大小: {len(audio_data)} bytes")
                    else:
                        raise Exception("未收到音频数据")

        except httpx.RequestError as e:
            raise Exception(f"豆包TTS网络请求失败: {str(e)}")

        return TTSResponse(audio_data=audio_base64)

    async def generate_batch_speech(
        self,
        sentences: List[str],
        output_dir: str,
        voice: Optional[str] = None,
        existing_files: Optional[Set[str]] = None,
        progress_callback: Optional[callable] = None,
        api_url: Optional[str] = None
    ) -> List[str]:
        """
        批量生成语音
        - 只生成不存在的文件
        - 返回生成的文件列表

        参数:
            sentences: 要转换的句子列表
            output_dir: 输出目录
            voice: 语音ID
            existing_files: 已存在的音频文件集合（用于增量处理）
            progress_callback: 进度回调函数 (current: int, total: int, message: str)
            api_url: 自定义TTS服务地址，为空则使用系统默认

        返回:
            生成的文件名列表
        """
        if voice is None:
            voice = self.settings.KOKORO_DEFAULT_VOICE

        # 使用自定义API URL或系统默认
        tts_api_url = api_url if api_url else self.settings.KOKORO_API_URL

        if existing_files is None:
            existing_files = set()

        # 确保输出目录存在
        os.makedirs(output_dir, exist_ok=True)

        generated_files = []
        total = len(sentences)

        # 使用信号量限制并发
        semaphore = asyncio.Semaphore(3)

        async def generate_one(index: int, text: str) -> Optional[str]:
            nonlocal generated_files
            async with semaphore:
                # 生成文件名
                file_name = f"{index:03d}.mp3"
                file_path = os.path.join(output_dir, file_name)

                # 检查是否已存在
                if file_name in existing_files or os.path.exists(file_path):
                    return None

                try:
                    # 调用Kokoro API
                    async with httpx.AsyncClient(timeout=self.settings.TTS_TIMEOUT) as client:
                        payload = {
                            "model": "kokoro",
                            "input": text,
                            "voice": voice,
                            "response_format": "mp3",
                            "speed": 1.0
                        }
                        response = await client.post(tts_api_url, json=payload)

                        if response.status_code != 200:
                            print(f"TTS API returned {response.status_code}: {response.text}")
                            return None

                        # 保存文件
                        with open(file_path, "wb") as f:
                            f.write(response.content)

                        generated_files.append(file_name)

                        # 调用进度回调
                        if progress_callback:
                            try:
                                await progress_callback(len(generated_files), total, f"正在生成语音 ({len(generated_files)}/{total})...")
                            except Exception as e:
                                print(f"进度回调失败: {e}")

                        return file_name
                except Exception as e:
                    print(f"生成语音失败: {e}")
                    return None

        # 并发生成所有语音
        tasks = [generate_one(i, text) for i, text in enumerate(sentences)]
        await asyncio.gather(*tasks, return_exceptions=True)

        return generated_files


# 单例实例
tts_service = TTSService()
