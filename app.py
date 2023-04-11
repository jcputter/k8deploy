import logging
import time
import asyncio
import ipaddress

from aiobotocore.session import get_session
import uvicorn
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI, Request, HTTPException, Header, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from authlib.integrations.starlette_client import OAuth, OAuthError
from httpx import AsyncClient
from pydantic import BaseModel
from starlette.middleware.sessions import SessionMiddleware


from core import update, config, argocd

app = FastAPI(docs_url=None, redoc_url=None)
app.add_middleware(SessionMiddleware, secret_key=config.settings.fastapi_app_key)
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")
log = logging.getLogger("uvicorn.info")

oauth = OAuth()

oauth.register(
    name='google',
    client_id=config.settings.google_client_id,
    client_secret=config.settings.google_client_secret,
    server_metadata_url=config.settings.google_openid_endpoint,
    client_kwargs={
        'scope': 'openid email profile'
    }
)


@app.get('/login')
async def login(request: Request):
    redirect_uri = request.url_for('auth')
    return await oauth.google.authorize_redirect(request, redirect_uri)


@app.get('/auth')
async def auth(request: Request):
    try:
        token = await oauth.google.authorize_access_token(request)
    except OAuthError as error:
        return HTMLResponse(f'<h1>{error.error}</h1>')
    user = token.get('userinfo')
    if user:
        request.session['user'] = dict(user)
    return RedirectResponse(url='/')


class Deploy(BaseModel):
    app: str
    project: str
    image: str


@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    user = request.session.get('user')
    if user is None:
        return RedirectResponse(url='/login')
    return templates.TemplateResponse("deploy.html", context={"request": request, "user": user["name"]})


@app.post("/deploy")
async def deploy(deploy: Deploy, request: Request):
    user = request.session.get('user')
    loop = asyncio.get_event_loop()
    if user is None:
        raise HTTPException(status_code=401)
    log.info(f"Processing deploy request: {deploy.app}, env: {deploy.project}, image: {deploy.image},")
    await asyncio.gather(
        loop.run_in_executor(None, update.git_commit, deploy.project, deploy.app, deploy.image, user["name"])
    )
    return {"deployment": "OK"}


@app.post("/status")
async def status(deploy: Deploy, request: Request):
    user = request.session.get('user')
    if user is None:
        raise HTTPException(status_code=401)
    timeout = time.time() + 60 * 5
    while True:
        await asyncio.sleep(5)
        health_status = await argocd.health(deploy.app, deploy.project)
        if health_status["status"] == "Healthy" \
                and health_status["image"] == deploy.image or time.time() > timeout:
            return health_status


@app.get("/list_projects")
async def list_projects(request: Request):
    user = request.session.get('user')
    if user is None:
        raise HTTPException(status_code=401)
    projects = await argocd.list_projects()
    return projects


@app.get("/list_apps")
async def list_apps(project: str, request: Request):
    user = request.session.get('user')
    if user is None:
        raise HTTPException(status_code=401)
    apps = await argocd.list_apps(project)
    return apps[project]


@app.get("/list_images")
async def list_images(app: str, request: Request):
    user = request.session.get('user')
    if user is None:
        raise HTTPException(status_code=401)
    session = get_session()
    async with session.create_client('ecr') as client:
        repo = app
        try:
            jmespath_expression = f"reverse(sort_by(imageDetails, &to_string(imagePushedAt)))[*].imageTags"
            paginator = client.get_paginator('describe_images')
            iterator = paginator.paginate(repositoryName=app, PaginationConfig={'PageSize': 1000})
            filter_iterator = iterator.search(jmespath_expression)
            image_tags = [item async for i in filter_iterator for item in i if item]
            log.info(f"Found the following images {image_tags} for {repo}")
            return image_tags
        except client.exceptions.RepositoryNotFoundException:
            log.error(f"Repository {repo} not found")
            raise HTTPException(status_code=404)


@app.get("/healthz")
async def health_check():
    return {"Health": "OK"}


async def github_ip(request: Request):
    try:
        src_ip = ipaddress.ip_address(request.client.host)
    except ValueError:
        raise HTTPException(status_code=400, detail="Could not parse IP")
    async with AsyncClient() as client:
        allowlist = await client.get("https://api.github.com/meta")
    for valid_ip in allowlist.json()["hooks"]:
        if src_ip in ipaddress.ip_network(valid_ip):
            log.info(f"Received a Github Webhook request from {src_ip}")
            return
    else:
        log.info(f"Tsek! {src_ip} was not from Github")
        raise HTTPException(status_code=403, detail="Tsek!")


@app.post("/webhook", dependencies=[Depends(github_ip)])
async def receive_payload(request: Request, x_github_event: str = Header(...)):
    log.info("Processing Webhook Payload")
    if x_github_event == "workflow_job":
        payload = await request.json()
        if payload["action"] == "completed":
            await update.init()
        else:
            log.info("Workflow run still in progress...skipping update")
    elif x_github_event == "ping":
        return {"message": "Pong"}
    else:
        log.error("Could not process the request")
        return {"message": "Could not process the request"}


@app.on_event("startup")
async def task_scheduler():
    if config.settings.auto_update:
        log.info("Update Schedule enabled")
        scheduler = AsyncIOScheduler()
        scheduler.add_job(update.init, "interval",
                          seconds=config.settings.auto_update_interval, max_instances=1)
        scheduler.start()
    else:
        log.info("Update Schedule disabled")

if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", proxy_headers=True,
                forwarded_allow_ips="*", loop="uvloop", port=8080, workers=1)
