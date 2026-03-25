"""SSE (Server-Sent Events) 工具模块"""
import asyncio
import json
import logging
from typing import Optional, Callable, Awaitable, Any, Dict
from functools import partial

logger = logging.getLogger(__name__)


def format_sse_message(
    percentage: int,
    message: str,
    success: Optional[bool] = None,
    book_id: Optional[str] = None,
    **extra_data: Any
) -> str:
    """
    格式化 SSE 消息，对特殊字符进行转义

    参数:
        percentage: 进度百分比 (0-100)
        message: 消息内容
        success: 可选的 success 标志
        book_id: 可选的 book_id
        **extra_data: 其他额外数据字段

    返回:
        格式化的 SSE 消息字符串
    """
    # 转义特殊字符
    message = message.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n').replace('\r', '\\r')
    # 截断过长消息
    message = message[:500]

    data: Dict[str, Any] = {'percentage': percentage, 'message': message}
    if success is not None:
        data['success'] = success
    if book_id is not None:
        data['book_id'] = book_id
    # 添加额外数据
    data.update(extra_data)
    return f"data: {json.dumps(data)}\n\n"


class SSEProgressGenerator:
    """
    SSE 进度推送生成器

    用于替代重复的 SSE 进度推送逻辑

    使用示例:
        async def event_generator():
            generator = SSEProgressGenerator()

            async def progress_callback(percentage: int, message: str):
                await generator.queue.put({"percentage": percentage, "message": message})

            # 执行任务...
            await some_task(progress_callback)

            # 返回最终结果
            yield generator.format_success(100, "完成")
    """

    def __init__(self, timeout: float = 0.5):
        """
        初始化 SSE 进度生成器

        参数:
            timeout: 队列获取超时时间（秒）
        """
        self.queue: asyncio.Queue = asyncio.Queue()
        self.timeout = timeout
        self._task: Optional[asyncio.Task] = None
        self._done = False

    def format(self, percentage: int, message: str, **kwargs) -> str:
        """格式化 SSE 消息"""
        return format_sse_message(percentage, message, **kwargs)

    def format_success(self, percentage: int, message: str, **kwargs) -> str:
        """格式化成功消息"""
        return format_sse_message(percentage, message, success=True, **kwargs)

    def format_error(self, percentage: int, message: str, **kwargs) -> str:
        """格式化错误消息"""
        return format_sse_message(percentage, message, success=False, **kwargs)

    async def run_task(
        self,
        task_coro: Callable[[Callable, Any], Awaitable],
        *args: Any,
        extra_fields: Optional[Dict[str, Any]] = None,
        **kwargs: Any
    ) -> Any:
        """
        运行任务并收集进度

        参数:
            task_coro: 任务协程函数
            *args: 传递给任务的参数
            extra_fields: 额外字段，会添加到每条消息中
            **kwargs: 传递给任务的关键字参数

        返回:
            任务结果
        """
        # 创建包装的回调函数
        async def wrapped_callback(percentage: int, message: str, **extra):
            data = {"percentage": percentage, "message": message}
            if extra_fields:
                data.update(extra_fields)
            if extra:
                data.update(extra)
            await self.queue.put(data)

        # 创建包装的任务协程
        async def wrapped_task():
            try:
                # 尝试不同的回调签名
                try:
                    await task_coro(wrapped_callback, *args, **kwargs)
                except TypeError:
                    # 如果第一个签名失败，尝试传递普通回调
                    await task_coro(wrapped_callback)
            except Exception as e:
                logger.error(f"任务执行异常: {e}")
                await self.queue.put({"percentage": 0, "message": str(e), "_error": True})

        self._task = asyncio.create_task(wrapped_task())
        return await self._task

    def create_stream_response(
        self,
        final_message: str = "任务完成",
        success_result_attr: Optional[str] = None,
        error_message: str = "任务执行失败"
    ):
        """
        创建 SSE 流响应生成器

        参数:
            final_message: 完成时的默认消息
            success_result_attr: 成功结果对象的属性名（如 'message', 'success'）
            error_message: 错误消息前缀

        返回:
            异步生成器函数
        """
        async def event_generator():
            while not self._done:
                try:
                    data = await asyncio.wait_for(self.queue.get(), timeout=self.timeout)
                    # 检查是否是错误
                    if data.get("_error"):
                        yield format_sse_message(0, data["message"], False)
                        self._done = True
                        break
                    # 格式化并发送消息
                    yield format_sse_message(
                        data.get("percentage", 0),
                        data.get("message", ""),
                        **{"k": v for k, v in data.items() if not k.startswith("_")}
                    )
                except asyncio.TimeoutError:
                    # 检查任务是否完成
                    if self._task and self._task.done():
                        try:
                            result = self._task.result()
                            # 根据结果属性发送最终消息
                            if success_result_attr and hasattr(result, success_result_attr):
                                success = getattr(result, "success", True)
                                msg = getattr(result, success_result_attr, final_message)
                                yield format_sse_message(100, msg, success)
                            else:
                                yield format_sse_message(100, final_message, True)
                        except Exception as e:
                            logger.error(f"获取任务结果异常: {e}")
                            yield format_sse_message(0, f"{error_message}: {str(e)}", False)
                        self._done = True
                        break

        return event_generator


def create_sse_generator(
    task_func: Callable,
    *args: Any,
    final_message: str = "完成",
    result_message_attr: str = "message",
    result_success_attr: str = "success",
    **task_kwargs: Any
):
    """
    创建 SSE 生成器的便捷工厂函数

    这是一个简化的接口，适合大多数使用场景

    参数:
        task_func: 任务函数（如 book_service.import_book_with_progress）
        *args: 位置参数
        final_message: 完成时的默认消息
        result_message_attr: 结果对象的消息属性名
        result_success_attr: 结果对象的成功标志属性名
        **task_kwargs: 关键字参数

    返回:
        异步生成器函数
    """
    async def event_generator():
        queue: asyncio.Queue = asyncio.Queue()

        async def progress_callback(percentage: int, message: str):
            await queue.put({"percentage": percentage, "message": message})

        # 创建包装的任务
        async def wrapped_task():
            try:
                return await task_func(
                    progress_callback=progress_callback,
                    *args,
                    **task_kwargs
                )
            except Exception as e:
                logger.error(f"SSE任务异常: {e}")
                return type('Result', (), {
                    'success': False,
                    'message': str(e)
                })()

        task = asyncio.create_task(wrapped_task())

        while True:
            try:
                data = await asyncio.wait_for(queue.get(), timeout=0.5)
                yield format_sse_message(data["percentage"], data["message"])
            except asyncio.TimeoutError:
                if task.done():
                    try:
                        result = task.result()
                        success = getattr(result, result_success_attr, True)
                        message = getattr(result, result_message_attr, final_message)
                        yield format_sse_message(100, message, success)
                    except Exception as e:
                        logger.error(f"SSE结果获取异常: {e}")
                        yield format_sse_message(0, f"任务失败: {str(e)}", False)
                    break

        return

    return event_generator

