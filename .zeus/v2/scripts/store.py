import abc
import json
import os
import tempfile
from pathlib import Path

from filelock import FileLock


class AbstractStore(abc.ABC):
    """可插拔存储抽象基类，为 ZeusOpen v2 多 Agent 并行系统提供统一文件读写接口。"""

    @abc.abstractmethod
    def read_json(self, path: str) -> dict:
        """读取指定路径的 JSON 文件并返回字典。"""
        raise NotImplementedError

    @abc.abstractmethod
    def write_json(self, path: str, data: dict) -> None:
        """将字典以 JSON 格式写入指定路径。"""
        raise NotImplementedError

    @abc.abstractmethod
    def append_line(self, path: str, line: str) -> None:
        """以 UTF-8 追加模式写入一行（自动追加换行符）。"""
        raise NotImplementedError

    @abc.abstractmethod
    def lock(self, path: str):
        """返回一个上下文管理器，用于对指定路径进行文件级锁定。"""
        raise NotImplementedError

    @abc.abstractmethod
    def update_json_fields(
        self,
        path: str,
        *,
        list_key: str,
        id_field: str,
        updates: list[dict],
    ) -> None:
        """
        原子更新 JSON 文件中某个列表里的多个对象字段。

        参数：
            path: JSON 文件路径
            list_key: 顶层列表字段名（如 "tasks"）
            id_field: 列表项中用于匹配的唯一标识字段名（如 "id"）
            updates: 每个元素是一个 dict，必须包含 id_field 以及要更新的字段
        """
        raise NotImplementedError


class LocalStore(AbstractStore):
    """基于本地文件系统的默认存储实现，支持跨进程/跨线程文件锁与原子写。"""

    def __init__(self, base_dir: str | None = None):
        if base_dir is None:
            # 默认以 zeus-open 项目根目录为基准
            # __file__ -> .zeus/v2/scripts/store.py
            base_dir = Path(__file__).resolve().parent.parent.parent.parent
        self.base_dir = Path(base_dir)

    def _resolve(self, path: str) -> Path:
        """解析路径：绝对路径直接使用，相对路径基于 base_dir。"""
        p = Path(path)
        if p.is_absolute():
            return p
        return self.base_dir / p

    def read_json(self, path: str) -> dict:
        target = self._resolve(path)
        with open(target, "r", encoding="utf-8-sig") as f:
            return json.load(f)

    def write_json(self, path: str, data: dict) -> None:
        target = self._resolve(path)
        target.parent.mkdir(parents=True, exist_ok=True)

        # 在同目录下创建临时文件，确保原子重命名可用（Windows 兼容）
        fd, tmp_path = tempfile.mkstemp(dir=target.parent, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False)
            # 原子替换，防止并发写导致 JSON 损坏
            os.replace(tmp_path, target)
        except Exception:
            # 异常时清理临时文件
            try:
                os.unlink(tmp_path)
            except FileNotFoundError:
                pass
            raise

    def append_line(self, path: str, line: str) -> None:
        target = self._resolve(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        with open(target, "a", encoding="utf-8") as f:
            f.write(line + "\n")

    def lock(self, path: str):
        target = self._resolve(path)
        lock_path = str(target) + ".lock"
        # filelock.FileLock 本身已实现 __enter__ / __exit__，可直接作为上下文管理器返回
        return FileLock(lock_path, timeout=-1)

    def update_json_fields(
        self,
        path: str,
        *,
        list_key: str,
        id_field: str,
        updates: list[dict],
    ) -> None:
        target = self._resolve(path)
        with self.lock(path):
            data = self.read_json(path)
            items = data.get(list_key, [])
            if not isinstance(items, list):
                raise ValueError(f"Expected '{list_key}' to be a list in {path}")

            # 构建索引加速查找
            index_map = {item.get(id_field): idx for idx, item in enumerate(items) if id_field in item}

            for upd in updates:
                key_val = upd.get(id_field)
                if key_val is None:
                    continue
                idx = index_map.get(key_val)
                if idx is None:
                    continue
                items[idx].update(upd)

            self.write_json(path, data)


class TencentCosStore(AbstractStore):
    """腾讯云 COS 存储实现（预留骨架）。"""

    def read_json(self, path: str) -> dict:
        raise NotImplementedError("TencentCosStore.read_json is not implemented")

    def write_json(self, path: str, data: dict) -> None:
        raise NotImplementedError("TencentCosStore.write_json is not implemented")

    def append_line(self, path: str, line: str) -> None:
        raise NotImplementedError("TencentCosStore.append_line is not implemented")

    def lock(self, path: str):
        raise NotImplementedError("TencentCosStore.lock is not implemented")

    def update_json_fields(
        self,
        path: str,
        *,
        list_key: str,
        id_field: str,
        updates: list[dict],
    ) -> None:
        raise NotImplementedError("TencentCosStore.update_json_fields is not implemented")


class RedisStore(AbstractStore):
    """Redis 存储实现（预留骨架）。"""

    def read_json(self, path: str) -> dict:
        raise NotImplementedError("RedisStore.read_json is not implemented")

    def write_json(self, path: str, data: dict) -> None:
        raise NotImplementedError("RedisStore.write_json is not implemented")

    def append_line(self, path: str, line: str) -> None:
        raise NotImplementedError("RedisStore.append_line is not implemented")

    def lock(self, path: str):
        raise NotImplementedError("RedisStore.lock is not implemented")

    def update_json_fields(
        self,
        path: str,
        *,
        list_key: str,
        id_field: str,
        updates: list[dict],
    ) -> None:
        raise NotImplementedError("RedisStore.update_json_fields is not implemented")
