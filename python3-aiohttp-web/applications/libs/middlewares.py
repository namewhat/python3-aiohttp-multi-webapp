from core import web, get_redis, CSRF_CONF
from aiohttp_session import get_session


async def csrf_middleware(request, handler):
    async with get_redis() as redis: 
    	csrf_token = await redis.get('csrf_token')
    	session = await get_session(request)

    	if request.method in CSRF_CONF['methods'] and session.get('csrf_token') == csrf_token:
    		return await handler(request)
    	return web.json_response({'status': '403', 'msg': 'forbiden!'})
