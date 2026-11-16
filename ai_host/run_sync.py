from asgiref.sync import sync_to_async
from django.db import close_old_connections, connections


async def run_sync(function, *args, **kwargs):
    def invoke():
        close_old_connections()
        try:
            return function(*args, **kwargs)
        finally:
            close_old_connections()
            connections.close_all()

    return await sync_to_async(invoke, thread_sensitive=False)()
