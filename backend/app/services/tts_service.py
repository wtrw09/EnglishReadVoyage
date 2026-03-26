"""TTS服务用于文本转语音操作"""
import base64
import os
import hashlib
import httpx
import asyncio
import json
import logging
from typing import Optional, List, Set

from app.core.config import get_settings
from app.schemas.tts import TTSResponse
import uuid

logger = logging.getLogger(__name__)


class TTSService:
    """TTS相关业务逻辑的服务层"""

    def __init__(self):
        """使用配置初始化服务"""
        self.settings = get_settings()
        # edge-tts 限速：QPS不超过1
        self._edge_semaphore = asyncio.Semaphore(1)
        self._edge_last_request_time = 0.0
        self._edge_min_interval = 1.0  # 最小请求间隔（秒），确保QPS<=1
        # MiniMax TTS 限速：20 RPM，充值用户
        self._minimax_semaphore = asyncio.Semaphore(1)
        self._minimax_last_request_time = 0.0
        self._minimax_min_interval = 3.0  # 最小请求间隔（秒），确保 20 RPM

    def _validate_edge_voice(self, voice: str, default_voice: str) -> str:
        """
        验证 Edge-TTS 语音名称是否有效
        有效格式示例: en-US-AriaNeural, zh-CN-XiaoxiaoNeural
        """
        if not voice:
            return default_voice
        
        # 检查是否是有效的语音格式（包含 Neural 后缀或有效的语言前缀）
        voice_upper = voice.upper()
        valid_prefixes = ('en-', 'zh-', 'yue-', 'wuu-', 'mn-', 'cmn-', 'ja-', 'ko-')
        
        if ('NEURAL' in voice_upper or
            any(voice.startswith(prefix) for prefix in valid_prefixes)):
            return voice
        
        # 无效的语音名称，使用默认值
        logger.warning(f"Edge-TTS 语音名称无效: '{voice}'，使用默认值: '{default_voice}'")
        return default_voice

    async def generate_speech(
        self,
        text: str,
        voice: Optional[str] = None,
        api_url: Optional[str] = None,
        service_name: Optional[str] = None,
        doubao_app_id: Optional[str] = None,
        doubao_access_key: Optional[str] = None,
        doubao_resource_id: Optional[str] = None,
        siliconflow_api_key: Optional[str] = None,
        siliconflow_model: Optional[str] = None,
        minimax_api_key: Optional[str] = None,
        minimax_model: Optional[str] = None,
        speed: Optional[float] = None
    ) -> TTSResponse:
        """
        使用TTS API从文本生成语音

        参数:
            text: 要转换为语音的文本
            voice: 语音ID（默认为配置的默认语音）
            api_url: 自定义TTS服务地址，为空则使用系统默认
            service_name: 服务名称 'kokoro-tts', 'doubao-tts', 'siliconflow-tts', 'edge-tts' 或 'minimax-tts'
            doubao_app_id: 豆包APP ID
            doubao_access_key: 豆包Access Key
            doubao_resource_id: 豆包Resource ID
            siliconflow_api_key: 硅基流动API Key
            siliconflow_model: 硅基流动模型名称
            minimax_api_key: MiniMax API Key
            minimax_model: MiniMax模型名称
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

        if service_name == "siliconflow-tts":
            return await self.generate_siliconflow_speech(
                text=text,
                voice=voice,
                api_key=siliconflow_api_key,
                model=siliconflow_model
            )

        if service_name == "edge-tts":
            return await self.generate_edge_tts_speech(
                text=text,
                voice=voice,
                speed=speed
            )

        if service_name == "minimax-tts":
            logger.debug("进入 minimax-tts 分支")
            return await self.generate_minimax_speech(
                text=text,
                voice=voice,
                api_key=minimax_api_key,
                model=minimax_model,
                speed=speed
            )

        # 默认使用Kokoro
        if voice is None:
            voice = self.settings.KOKORO_DEFAULT_VOICE

        # 使用自定义API URL或系统默认
        tts_api_url = api_url if api_url else self.settings.KOKORO_API_URL

        # 调用Kokoro Docker API
        logger.info(f"调用TTS API: {tts_api_url}, voice={voice}, speed={speed}, text={text[:50]}...")
        async with httpx.AsyncClient(timeout=self.settings.TTS_TIMEOUT) as client:
            payload = {
                "model": "kokoro",
                "input": text,
                "voice": voice,
                "response_format": "mp3",
                "speed": speed if speed is not None else 1.0
            }
            logger.debug(f"TTS请求payload: {payload}")
            response = await client.post(tts_api_url, json=payload)
            logger.info(f"TTS API响应: status={response.status_code}")

            if response.status_code != 200:
                logger.error(f"TTS API错误: {response.text}")
                raise Exception(
                    f"TTS API returned {response.status_code}: {response.text}"
                )

            # 检查响应内容是否为空
            if not response.content or len(response.content) == 0:
                logger.warning(f"TTS API返回空内容: status={response.status_code}")
                raise Exception("未收到音频数据")

            # 返回音频数据（base64编码）
            audio_base64 = base64.b64encode(response.content).decode('utf-8')
            logger.info(f"TTS音频生成成功, 大小: {len(response.content)} bytes")

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

        logger.info(f"调用豆包TTS API: {url}, voice={voice}, resource_id={resource_id}, speed={speed}")
        logger.debug(f"  text={text[:50]}...")

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                # 使用 stream 方法进行流式请求
                async with client.stream("POST", url, headers=headers, json=payload) as response:
                    if response.status_code != 200:
                        error_text = await response.aread()
                        logger.warning(f"豆包TTS API错误: {response.status_code}, {error_text}")
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
                                logger.warning(f"豆包TTS错误: {data}")
                                break
                        except json.JSONDecodeError:
                            continue

                    if audio_data:
                        # 返回音频数据（base64编码）
                        audio_base64 = base64.b64encode(audio_data).decode('utf-8')
                        logger.info(f"豆包TTS生成成功, 大小: {len(audio_data)} bytes")
                    else:
                        raise Exception("未收到音频数据")

        except httpx.RequestError as e:
            raise Exception(f"豆包TTS网络请求失败: {str(e)}")

        return TTSResponse(audio_data=audio_base64)

    async def generate_siliconflow_speech(
        self,
        text: str,
        voice: Optional[str] = None,
        api_key: Optional[str] = None,
        model: Optional[str] = None
    ) -> TTSResponse:
        """
        使用硅基流动TTS API从文本生成语音

        参数:
            text: 要转换为语音的文本
            voice: 语音类型 (anna, alex, bella, benjiamin, charles, claire, david, diana)
            api_key: 硅基流动API Key
            model: 模型名称

        返回:
            包含音频数据的TTSResponse

        异常:
            Exception: 如果TTS API调用失败
        """
        # 使用默认值
        if voice is None:
            voice = self.settings.SILICONFLOW_DEFAULT_VOICE
        if model is None:
            model = self.settings.SILICONFLOW_DEFAULT_MODEL
        if not api_key:
            raise Exception("硅基流动TTS需要配置api_key")

        # 调用硅基流动TTS API
        url = self.settings.SILICONFLOW_API_URL
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        # voice格式为 "模型名:语音类型"
        full_voice = f"{model}:{voice}"

        payload = {
            "model": model,
            "input": text,
            "voice": full_voice,
            "response_format": "mp3",
            "stream": True
        }

        logger.info(f"调用硅基流动TTS API: {url}, model={model}, voice={full_voice}")
        logger.debug(f"  text={text[:50]}...")

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                # 使用 stream 方法进行流式请求
                async with client.stream("POST", url, headers=headers, json=payload) as response:
                    if response.status_code != 200:
                        error_text = await response.aread()
                        logger.warning(f"硅基流动TTS API错误: {response.status_code}, {error_text}")
                        raise Exception(f"硅基流动TTS API returned {response.status_code}: {error_text}")

                    # 流式读取音频数据
                    audio_data = bytearray()
                    async for chunk in response.aiter_bytes():
                        if chunk:
                            audio_data.extend(chunk)

                    if audio_data:
                        # 返回音频数据（base64编码）
                        audio_base64 = base64.b64encode(audio_data).decode('utf-8')
                        logger.info(f"硅基流动TTS生成成功, 大小: {len(audio_data)} bytes")
                    else:
                        raise Exception("未收到音频数据")

        except httpx.RequestError as e:
            raise Exception(f"硅基流动TTS网络请求失败: {str(e)}")

        return TTSResponse(audio_data=audio_base64)

    async def generate_edge_tts_speech(
        self,
        text: str,
        voice: Optional[str] = None,
        speed: Optional[float] = None
    ) -> TTSResponse:
        """
        使用Edge-TTS (微软Edge在线TTS) 从文本生成语音
        基于 edge-tts Python 库的实现原理，直接调用 Edge 语音合成服务

        参数:
            text: 要转换为语音的文本
            voice: 语音ID (如 en-US-AriaNeural, en-GB-SoniaNeural)
            speed: 朗读速度 (0.5-2.0)

        返回:
            包含音频数据的TTSResponse

        异常:
            Exception: 如果TTS API调用失败
        """
        # 使用默认值
        if voice is None or voice.strip() == "":
            voice = self.settings.EDGE_TTS_DEFAULT_VOICE
            logger.info(f"使用默认Edge-TTS语音: {voice}")
        
        # 验证语音名称是否有效（无效时使用默认语音）
        voice = self._validate_edge_voice(voice, self.settings.EDGE_TTS_DEFAULT_VOICE)
        
        if speed is None or speed <= 0:
            speed = 1.0

        # 将速度转换为百分比格式 (0.5 -> -50%, 1.0 -> 0%, 2.0 -> +100%)
        rate_percent = int((speed - 1.0) * 100)
        # 确保 rate_str 始终有效
        rate_str = f"{rate_percent:+d}%"

        logger.info(f"调用Edge-TTS API: voice={voice}, speed={speed}, rate={rate_str}")
        logger.debug(f"  text长度={len(text)}, text前100字符={text[:100]!r}")

        # Edge-TTS 限速控制：确保QPS<=1
        async with self._edge_semaphore:
            current_time = asyncio.get_event_loop().time()
            time_since_last = current_time - self._edge_last_request_time
            if time_since_last < self._edge_min_interval:
                wait_time = self._edge_min_interval - time_since_last
                logger.debug(f"Edge-TTS 限速等待 {wait_time:.2f} 秒")
                await asyncio.sleep(wait_time)
            self._edge_last_request_time = asyncio.get_event_loop().time()

        # 重试配置 - 使用指数退避策略
        max_retries = 5
        base_retry_delay = 2  # 基础重试延迟（秒）
        last_error = None

        for attempt in range(max_retries):
            try:
                import tempfile
                import subprocess
                import shutil
                import sys
                import os

                # 首先尝试检测当前Python的虚拟环境路径
                venv_path = None
                # 检查是否存在 pyvenv.cfg 文件（虚拟环境标识）
                base_dir = os.path.dirname(os.path.dirname(sys.executable))
                pyvenv_cfg = os.path.join(base_dir, 'pyvenv.cfg')
                if os.path.exists(pyvenv_cfg):
                    # 当前在虚拟环境中，Scripts目录就在该目录下
                    venv_scripts = os.path.join(base_dir, 'Scripts')
                    if os.path.exists(venv_scripts):
                        venv_path = venv_scripts
                        logger.debug(f"检测到虚拟环境路径: {venv_path}")

                # 根据操作系统选择不同的路径列表
                if sys.platform == 'win32':
                    # Windows 路径
                    possible_paths = [
                        r"F:\PyProject\EnglishReadVoyage\backend\.venv\Scripts\edge-tts.exe",
                        r"C:\Users\%USERNAME%\AppData\Local\Programs\Python\Python313\Scripts\edge-tts.exe",
                        r"C:\Users\%USERNAME%\AppData\Local\Programs\Python\Python312\Scripts\edge-tts.exe",
                        r"C:\Users\%USERNAME%\AppData\Local\Programs\Python\Python311\Scripts\edge-tts.exe",
                    ]
                    # 如果检测到虚拟环境，优先使用
                    if venv_path:
                        possible_paths.insert(0, os.path.join(venv_path, 'edge-tts.exe'))
                else:
                    # Linux 路径 (Docker 容器)
                    possible_paths = [
                        "/root/.local/bin/edge-tts",  # Docker 容器中 pip install --user 安装的路径
                        "/usr/local/bin/edge-tts",
                        "/usr/bin/edge-tts",
                        "/app/.venv/bin/edge-tts",
                        "/opt/python3.11/bin/edge-tts",
                    ]

                # 先尝试常见路径
                edge_tts_path = None
                for path in possible_paths:
                    expanded_path = os.path.expandvars(path)
                    if os.path.exists(expanded_path):
                        edge_tts_path = expanded_path
                        logger.debug(f"使用备用路径: {edge_tts_path}")
                        break

                # 如果找不到，尝试shutil.which (这个在Linux/Docker中最可靠)
                if not edge_tts_path:
                    edge_tts_path = shutil.which("edge-tts")
                    logger.debug(f"edge-tts 路径查找结果: {edge_tts_path}")

                # 如果还找不到，抛出错误
                if not edge_tts_path:
                    # 打印当前PATH环境变量，帮助调试
                    logger.debug(f"当前PATH: {os.environ.get('PATH', '')[:200]}...")
                    raise FileNotFoundError("edge-tts 命令未找到")

                # 创建临时输出文件（使用系统临时目录）
                import uuid
                temp_dir = tempfile.gettempdir()
                unique_id = uuid.uuid4().hex[:8]
                output_file = os.path.join(temp_dir, f"edge_tts_{os.getpid()}_{unique_id}.mp3")

                try:
                    # 将文本写入临时文件，避免命令行参数解析问题
                    text_file = os.path.join(temp_dir, f"edge_tts_text_{os.getpid()}_{unique_id}.txt")
                    with open(text_file, 'w', encoding='utf-8') as f:
                        f.write(text)

                    # 构建 edge-tts 命令 (使用 --file= 格式避免特殊字符问题)
                    cmd = [
                        edge_tts_path,
                        "--voice", voice,
                        f"--rate={rate_str}",
                        f"--file={text_file}",
                        "--write-media", output_file
                    ]

                    logger.info(f"执行Edge-TTS命令: path={edge_tts_path}, voice={voice}, rate={rate_str}")
                    logger.debug(f"  text={text[:50]!r}..., output_file={output_file}")

                    # 在Windows上使用线程池执行子进程，避免NotImplementedError
                    import sys
                    if sys.platform == 'win32':
                        # Windows: 使用线程池运行同步subprocess
                        from concurrent.futures import ThreadPoolExecutor
                        import subprocess

                        def run_edge_tts():
                            try:
                                # 不使用 text=True，避免编码问题
                                result = subprocess.run(
                                    cmd,
                                    capture_output=True,
                                    timeout=60
                                )
                                # 手动解码，处理可能的编码错误
                                stdout_text = ""
                                stderr_text = ""
                                try:
                                    stdout_text = result.stdout.decode('utf-8', errors='ignore') if result.stdout else ""
                                except Exception:
                                    pass
                                try:
                                    stderr_text = result.stderr.decode('utf-8', errors='ignore') if result.stderr else ""
                                except Exception:
                                    pass
                                return result.returncode, stdout_text, stderr_text
                            except subprocess.TimeoutExpired:
                                return -1, "", "Timeout"
                            except Exception as e:
                                return -1, "", str(e)

                        loop = asyncio.get_event_loop()
                        with ThreadPoolExecutor() as pool:
                            returncode, stdout_text, stderr_text = await loop.run_in_executor(pool, run_edge_tts)
                    else:
                        # Linux/Mac: 使用异步子进程
                        process = await asyncio.create_subprocess_exec(
                            *cmd,
                            stdout=asyncio.subprocess.PIPE,
                            stderr=asyncio.subprocess.PIPE
                        )

                        try:
                            stdout, stderr = await asyncio.wait_for(
                                process.communicate(),
                                timeout=60
                            )
                            returncode = process.returncode
                            stdout_text = stdout.decode('utf-8') if stdout else ""
                            stderr_text = stderr.decode('utf-8') if stderr else ""
                        except asyncio.TimeoutError:
                            process.kill()
                            await process.wait()
                            raise Exception("Edge-TTS执行超时")

                    # 检查是否是 503 错误
                    if returncode != 0:
                        error_msg = stderr_text
                        # 检查是否是 503 服务不可用错误
                        if "503" in error_msg or "WSServerHandshakeError" in error_msg:
                            last_error = Exception(f"Edge-TTS服务暂时不可用 (503): {error_msg[:100]}")
                            # 使用指数退避策略计算等待时间
                            retry_delay = min(base_retry_delay * (2 ** attempt), 10)
                            logger.warning(f"Edge-TTS 503错误，第 {attempt + 1} 次尝试失败，{retry_delay}秒后重试...")
                            # 等待后重试
                            await asyncio.sleep(retry_delay)
                            continue
                        else:
                            logger.error(f"Edge-TTS错误: stderr={stderr_text}, stdout={stdout_text}")
                            raise Exception(f"Edge-TTS执行失败: {stderr_text}")

                    # 读取生成的音频文件
                    logger.debug(f"检查输出文件: {output_file}, exists={os.path.exists(output_file)}")
                    with open(output_file, 'rb') as f:
                        audio_data = f.read()

                    if not audio_data or len(audio_data) == 0:
                        logger.error(f"Edge-TTS错误: 文件为空, returncode={returncode}")
                        raise Exception("Edge-TTS未生成音频数据")

                    # 返回base64编码的音频数据
                    audio_base64 = base64.b64encode(audio_data).decode('utf-8')
                    logger.info(f"Edge-TTS生成成功, 大小: {len(audio_data)} bytes")

                finally:
                    # 清理临时文件
                    try:
                        if os.path.exists(output_file):
                            os.unlink(output_file)
                            logger.debug(f"已清理临时文件: {output_file}")
                        if os.path.exists(text_file):
                            os.unlink(text_file)
                            logger.debug(f"已清理临时文本文件: {text_file}")
                    except Exception as e:
                        logger.warning(f"清理临时文件失败: {e}")

                # 成功，跳出重试循环
                break

            except FileNotFoundError as e:
                logger.error(f"Edge-TTS命令未找到: {e}")
                raise Exception("Edge-TTS未安装，请运行: pip install edge-tts")
            except Exception as e:
                # 如果是 503 错误，已经在循环中处理了
                if "503" in str(e) or "WSServerHandshakeError" in str(e):
                    last_error = e
                    continue
                # 其他错误直接抛出
                import traceback
                error_detail = traceback.format_exc()
                logger.error(f"Edge-TTS详细错误: {error_detail}")
                raise Exception(f"Edge-TTS生成失败: {str(e)}")

        # 如果所有重试都失败
        if last_error:
            raise Exception(f"Edge-TTS服务暂时不可用，已重试{max_retries}次，请稍后重试")

        return TTSResponse(audio_data=audio_base64)

    async def generate_minimax_speech(
        self,
        text: str,
        voice: Optional[str] = None,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        speed: Optional[float] = None
    ) -> TTSResponse:
        """
        使用 MiniMax TTS API 从文本生成语音
        - 支持并发控制（QPS <= 1）
        - 支持限流重试机制

        参数:
            text: 要转换为语音的文本
            voice: 语音ID
            api_key: MiniMax API Key
            model: 模型名称
            speed: 朗读速度 (0.5-2.0)

        返回:
            包含音频数据的TTSResponse

        异常:
            Exception: 如果TTS API调用失败
        """
        import os

        # 使用默认值
        if voice is None:
            voice = self.settings.MINIMAX_DEFAULT_VOICE
        if model is None:
            model = self.settings.MINIMAX_DEFAULT_MODEL
        if speed is None:
            speed = 1.0
        if not api_key:
            raise Exception("MiniMax TTS需要配置API Key，请在朗读设置中填写")

        masked_key = "已设置" if api_key else "未设置"
        logger.debug(f"MiniMax TTS配置: api_key={masked_key}, model={model}, voice={voice}, speed={speed}")

        url = self.settings.MINIMAX_API_URL
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        # 构建请求体
        payload = {
            "model": model,
            "text": text,
            "stream": False,
            "voice_setting": {
                "voice_id": voice,
                "speed": speed,
                "vol": 1,
                "pitch": 0
            },
            "audio_setting": {
                "sample_rate": 32000,
                "bitrate": 128000,
                "format": "mp3",
                "channel": 1
            }
        }

        logger.info(f"调用MiniMax TTS API: {url}, model={model}, voice={voice}, speed={speed}")
        logger.debug(f"  text长度={len(text)}, text前50字符={text[:50]}...")

        # MiniMax TTS 限流控制：确保 20 RPM
        async with self._minimax_semaphore:
            current_time = asyncio.get_event_loop().time()
            time_since_last = current_time - self._minimax_last_request_time
            if time_since_last < self._minimax_min_interval:
                wait_time = self._minimax_min_interval - time_since_last
                logger.debug(f"MiniMax TTS 限流等待 {wait_time:.2f} 秒")
                await asyncio.sleep(wait_time)
            self._minimax_last_request_time = asyncio.get_event_loop().time()

        # 重试配置（限流通常约1分钟恢复）
        max_retries = 3
        retry_delay = 60  # 秒
        last_error = None

        for attempt in range(max_retries):
            try:
                async with httpx.AsyncClient(timeout=60.0) as client:
                    response = await client.post(url, headers=headers, json=payload)

                    if response.status_code != 200:
                        error_text = response.text
                        # 检查是否是限流错误
                        if response.status_code in (429, 503):
                            last_error = Exception(f"MiniMax TTS限流 ({response.status_code}): {error_text[:200]}")
                            logger.warning(f"MiniMax TTS 限流，第 {attempt + 1} 次尝试失败，{retry_delay}秒后重试...")
                            await asyncio.sleep(retry_delay)
                            continue
                        raise Exception(f"MiniMax TTS API returned {response.status_code}: {error_text}")

                    result = response.json()

                    # 检查业务错误码
                    if result.get("base_resp", {}).get("status_code", 0) != 0:
                        status_msg = result.get("base_resp", {}).get("status_msg", "未知错误")
                        raise Exception(f"MiniMax TTS业务错误: {status_msg}")

                    # 解析 hex 编码的音频
                    audio_hex = result.get("data", {}).get("audio")
                    if not audio_hex:
                        raise Exception("未收到音频数据")

                    audio_data = bytes.fromhex(audio_hex)
                    audio_base64 = base64.b64encode(audio_data).decode('utf-8')
                    logger.info(f"MiniMax TTS生成成功, 大小: {len(audio_data)} bytes")
                    break

            except httpx.RequestError as e:
                last_error = Exception(f"MiniMax TTS网络请求失败: {str(e)}")
                logger.warning(f"MiniMax TTS 网络错误，第 {attempt + 1} 次尝试失败，{retry_delay}秒后重试...")
                await asyncio.sleep(retry_delay)
                continue

        # 所有重试都失败
        if last_error:
            raise last_error

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
                            logger.warning(f"TTS API returned {response.status_code}: {response.text}")
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
                                logger.warning(f"进度回调失败: {e}")

                        return file_name
                except Exception as e:
                    logger.error(f"生成语音失败: {e}")
                    return None

        # 并发生成所有语音
        tasks = [generate_one(i, text) for i, text in enumerate(sentences)]
        await asyncio.gather(*tasks, return_exceptions=True)

        return generated_files


# 单例实例
tts_service = TTSService()
