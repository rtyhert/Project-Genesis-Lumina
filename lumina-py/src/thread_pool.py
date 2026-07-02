from concurrent.futures import ThreadPoolExecutor

_IO_THREAD_POOL = ThreadPoolExecutor(
    max_workers=4,
    thread_name_prefix="lumina-io",
)


def get_io_executor() -> ThreadPoolExecutor:
    return _IO_THREAD_POOL


def shutdown_io_executor(wait: bool = True):
    _IO_THREAD_POOL.shutdown(wait=wait)
