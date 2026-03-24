"""翻译服务 - 百度翻译API"""
import asyncio
import hashlib
import urllib.parse
from typing import Optional, Tuple

import httpx


class TranslationResult:
    """翻译结果类，包含翻译文本和错误信息"""
    def __init__(self, translation: Optional[str] = None, error: Optional[str] = None):
        self.translation = translation
        self.error = error
        self.success = translation is not None

    def __repr__(self):
        if self.success:
            return f"TranslationResult(success=True, translation='{self.translation[:50]}...')"
        else:
            return f"TranslationResult(success=False, error='{self.error}')"


class TranslationService:
    """翻译服务类"""

    def __init__(self):
        self.api_url = "https://fanyi-api.baidu.com/api/trans/vip/translate"
        self._client: Optional[httpx.AsyncClient] = None
        # 限制QPS不超过10，使用信号量控制并发
        # 每次请求间隔至少0.1秒，确保QPS<=10
        self._semaphore = asyncio.Semaphore(10)
        self._last_request_time = 0.0
        self._min_interval = 0.1  # 最小请求间隔（秒）

    async def get_client(self) -> httpx.AsyncClient:
        """获取或创建HTTP客户端（连接池复用）"""
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=10.0,
                limits=httpx.Limits(max_connections=10, max_keepalive_connections=5)
            )
        return self._client

    async def translate_with_baidu(
        self,
        text: str,
        from_lang: str = "en",
        to_lang: str = "zh",
        app_id: str = "",
        app_key: str = ""
    ) -> Optional[str]:
        """
        使用百度翻译API翻译文本

        Args:
            text: 要翻译的文本
            from_lang: 源语言
            to_lang: 目标语言
            app_id: 百度翻译APP ID
            app_key: 百度翻译APP Key

        Returns:
            翻译结果文本，失败返回None
        """
        if not text or not app_id or not app_key:
            return None

        # 百度翻译API签名计算
        import random
        salt = str(random.randint(32768, 65536))
        sign = self._calculate_sign(text, app_id, salt, app_key)

        params = {
            "q": text,
            "from": from_lang,
            "to": to_lang,
            "appid": app_id,
            "salt": salt,
            "sign": sign
        }

        # 限速控制：确保两次请求之间至少间隔0.1秒
        async with self._semaphore:
            current_time = asyncio.get_event_loop().time()
            time_since_last = current_time - self._last_request_time
            if time_since_last < self._min_interval:
                await asyncio.sleep(self._min_interval - time_since_last)
            self._last_request_time = asyncio.get_event_loop().time()

            try:
                client = await self.get_client()
                response = await client.post(self.api_url, data=params)
                result = response.json()

                trans_result = result.get("trans_result")
                if trans_result and len(trans_result) > 0:
                    return trans_result[0]["dst"]
                elif "error_code" in result:
                    print(f"百度翻译API错误: {result.get('error_msg', '未知错误')}")
                    return None
                else:
                    print(f"百度翻译API返回异常: {result}")
                    return None

            except Exception as e:
                print(f"百度翻译请求失败: {e}")
                return None

        return None

    async def translate_with_result(
        self,
        text: str,
        from_lang: str = "en",
        to_lang: str = "zh",
        app_id: str = "",
        app_key: str = ""
    ) -> TranslationResult:
        """
        使用百度翻译API翻译文本，返回详细结果

        Args:
            text: 要翻译的文本
            from_lang: 源语言
            to_lang: 目标语言
            app_id: 百度翻译APP ID
            app_key: 百度翻译APP Key

        Returns:
            TranslationResult对象，包含翻译结果和错误信息
        """
        if not text:
            return TranslationResult(error="文本为空")

        if not app_id or not app_key:
            return TranslationResult(error="APP ID或APP Key为空")

        # 百度翻译API签名计算
        import random
        salt = str(random.randint(32768, 65536))
        sign = self._calculate_sign(text, app_id, salt, app_key)

        params = {
            "q": text,
            "from": from_lang,
            "to": to_lang,
            "appid": app_id,
            "salt": salt,
            "sign": sign
        }

        # 限速控制：确保两次请求之间至少间隔0.1秒
        async with self._semaphore:
            current_time = asyncio.get_event_loop().time()
            time_since_last = current_time - self._last_request_time
            if time_since_last < self._min_interval:
                await asyncio.sleep(self._min_interval - time_since_last)
            self._last_request_time = asyncio.get_event_loop().time()

            try:
                client = await self.get_client()
                response = await client.post(self.api_url, data=params)
                result = response.json()

                trans_result = result.get("trans_result")
                if trans_result and len(trans_result) > 0:
                    return TranslationResult(translation=trans_result[0]["dst"])
                elif "error_code" in result:
                    error_msg = result.get('error_msg', '未知错误')
                    print(f"百度翻译API错误: {error_msg}")
                    return TranslationResult(error=f"API错误: {error_msg}")
                else:
                    print(f"百度翻译API返回异常: {result}")
                    return TranslationResult(error=f"API返回异常: {result}")

            except Exception as e:
                print(f"百度翻译请求失败: {e}")
                return TranslationResult(error=f"请求失败: {str(e)}")

        return TranslationResult(error="未知错误")

    def _calculate_sign(self, text: str, app_id: str, salt: str, app_key: str) -> str:
        """计算百度翻译API签名"""
        sign_str = f"{app_id}{text}{salt}{app_key}"
        return hashlib.md5(sign_str.encode('utf-8')).hexdigest()


# 全局翻译服务实例
translation_service = TranslationService()
