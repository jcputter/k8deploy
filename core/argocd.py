import json
import logging
import re

import httpx

from core import config

log = logging.getLogger("uvicorn.info")


async def list_projects():
    argo_endpoint = "projects"
    async with httpx.AsyncClient(headers=config.settings.argocd_auth_header) as client:
        log.info("Retrieving a list of projects from AgroCD..")
        resp_body = await client.get("".join([config.settings.argocd_base_url, argo_endpoint]))
        response = resp_body.json()["items"]
        projects = [project["metadata"]["name"] for project in response
                    if(not project["metadata"]["name"] in config.settings.ignored_projects)]
        log.info(f"Found the following projects {projects}")
        return projects


async def list_apps(project: str):
    argo_endpoint = f"applications?project={project}&selector=mm-env={project}"
    async with httpx.AsyncClient(headers=config.settings.argocd_auth_header) as client:
        log.info("Retrieving a list of apps available from AgroCD..")
        resp_body = await client.get("".join([config.settings.argocd_base_url, argo_endpoint]))
        response = resp_body.json()["items"]
        try:
            apps = [app["metadata"]["labels"]["mm-service"] for app in response
                    if(not app["metadata"]["name"] == project)]
        except TypeError:
            log.warning(f"No applications found for {project} environment")
        else:
            log.info(f"Found the following applications for {project} {apps}")
            return {project: apps}


async def get_tag(env: str, service: str):
    argo_endpoint = f"applications/{env}-{service}/resource?namespace={env}&resourceName={env}-{service}&kind" \
                    f"=Deployment&group=apps&version=v1"
    async with httpx.AsyncClient(headers=config.settings.argocd_auth_header) as client:
        try:
            resp_body = await client.get("".join([config.settings.argocd_base_url, argo_endpoint]))
            manifest = resp_body.json()["manifest"]
            spec = json.loads(manifest)
        except KeyError:
            log.error(f"Could not find app manifest for {service}, check app itself or naming standard?")
        else:
            try:
                if spec["metadata"]["annotations"][config.settings.autodeploy_annotation][:] == "true":
                    tag = spec["spec"]["template"]["spec"]["containers"][0]["image"].rpartition(":")[-1]
                    log.info(f"{service} is configured for Auto Deploy in {env}")
                else:
                    log.warning(f"{service} is not configured for Auto Deploy")
            except TypeError:
                log.error(f"{service} missing {config.settings.autodeploy_annotation}")
            except KeyError:
                log.error(f"{service} missing {config.settings.autodeploy_annotation}")
            else:
                return {"project": env, "service": service, "tag": tag}


async def health(app: str, project: str):
    argo_endpoint = f"applications?name={project}-{app}&project={project}"
    app = re.compile(f".*{app}*")
    async with httpx.AsyncClient(headers=config.settings.argocd_auth_header, timeout=60) as client:
        resp_body = await client.get("".join([config.settings.argocd_base_url, argo_endpoint]))
        status = resp_body.json()["items"][0]["status"]["health"]["status"]
        image = "".join(list(filter(app.match, resp_body.json()["items"][0]["status"]["summary"]["images"])))
        return {"status": status, "image": image.rpartition(":")[-1]}
