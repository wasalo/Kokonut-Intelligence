"""Bound sensor request bytes before JSON parsing, preserving signed evidence."""

import asyncio


class SensorBodyLimit:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope.get("method") != "POST":
            return await self.app(scope, receive, send)
        limit = 262144 if scope.get("path", "").endswith("/readings/batch") else 10240

        async def reject(status, message):
            await send({"type": "http.response.start", "status": status,
                        "headers": [(b"content-type", b"application/json")]})
            await send({"type": "http.response.body", "body": message})

        buffer = bytearray()
        size = 0
        try:
            async with asyncio.timeout(10):
                while True:
                    message = await receive()
                    if message["type"] == "http.disconnect":
                        return
                    if message["type"] != "http.request":
                        continue
                    chunk = message.get("body", b"")
                    size += len(chunk)
                    if size > limit:
                        return await reject(413, b'{"detail":"Sensor request body too large"}')
                    buffer.extend(chunk)
                    if not message.get("more_body", False):
                        break
        except TimeoutError:
            return await reject(408, b'{"detail":"Sensor request body timeout"}')

        body = bytes(buffer)
        delivered = False

        async def bounded_receive():
            nonlocal delivered
            if not delivered:
                delivered = True
                return {"type": "http.request", "body": body, "more_body": False}
            return await receive()

        await self.app(scope, bounded_receive, send)
