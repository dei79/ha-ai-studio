"""Local path-stripping proxy for Ingress integration checks, NOT an HA auth emulator."""
from aiohttp import ClientSession, web
PREFIX='/api/hassio_ingress/dev-check/'
async def proxy(request):
    suffix=request.path[len(PREFIX):]
    headers={k:v for k,v in request.headers.items() if k.lower() not in ('host','content-length','connection','accept-encoding')}
    headers['Host']='localhost:8099';headers['X-Ingress-Path']=PREFIX.rstrip('/')
    async with ClientSession() as session:
        async with session.request(request.method,'http://studio:8099/'+suffix,params=request.query,data=await request.read(),headers=headers) as response:
            content=await response.read()
            forwarded={k:v for k,v in response.headers.items() if k.lower() not in ('content-length','transfer-encoding','connection','content-encoding')}
            return web.Response(status=response.status,body=content,headers=forwarded)
app=web.Application()
app.router.add_route('*',PREFIX+'{tail:.*}',proxy)
web.run_app(app,host='0.0.0.0',port=8100,access_log=None)
