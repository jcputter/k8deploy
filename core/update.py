import time
import logging
import asyncio
import httpx
from aiobotocore.session import get_session
import git
import ruamel.yaml
import tempfile
from jinja2 import Environment, FileSystemLoader
from core import config, argocd

log = logging.getLogger("uvicorn.info")


async def send_slack(app: str, project: str, tag: str, user="autodeploy"):
    if config.settings.slack_enable:
        branch = tag.split(".")[0]
        build_id = tag.split(".")[-1]
        commit = tag.split(".")[1].split(".")[0]
        file_loader = FileSystemLoader("./templates")
        slack_tmpl = Environment(autoescape=True, loader=file_loader)
        template = slack_tmpl.get_template("slack.jinja")
        message = template.render(service=app, tag=tag, project=project,
                                  branch=branch, build_id=build_id, commit=commit, user=user)
        async with httpx.AsyncClient(headers={'Content-Type': 'application/json'}) as client:
            request = await client.post(config.settings.slack_webhook, data=message)
            if request.status_code != 200:
                log.error("Slack message failed")
            else:
                log.info("Slack message sent")
    else:
        log.warning("Slack notifications are disabled")


async def latest_image(service: dict):
    session = get_session()
    async with session.create_client('ecr') as client:
        loop = asyncio.get_event_loop()
        branch = service['tag'].split(".")[0]
        tag = service['tag']
        app = service['service']
        project = service['project']
        jmespath_expression = f"sort_by(imageDetails, &to_string(imagePushedAt))[*].imageTags[? contains(@,'{branch}')]"
        paginator = client.get_paginator('describe_images')
        iterator = paginator.paginate(repositoryName=app, PaginationConfig={'PageSize': 1000})
        filter_iterator = iterator.search(jmespath_expression)
        try:
            latest_tag = [item async for i in filter_iterator for item in i if item][-1]
            if tag != latest_tag:
                log.info(f"Update Available for {app}/{project} -> CURRENT:{tag} LATEST:{latest_tag}")
                result = await asyncio.gather(loop.run_in_executor(None, git_commit, project, app, latest_tag))
                return result
            else:
                log.info(f"Seems like {project}-{app} is running the latest version")
        except IndexError:
            log.warning(f"Repo for {app} might be empty or invalid repo")


def git_commit(project: str, app: str, tag: str, user="autodeploy"):
    log.info(f"Checking out {config.settings.git_repo}")
    with tempfile.TemporaryDirectory(dir=".", prefix=f"{project}-{app}-") as tmpdir:
        git.Repo.clone_from(config.settings.git_repo, tmpdir, depth=1)
        repo = git.Repo(tmpdir)
        repo.create_remote("upstream", url=config.settings.git_repo)
        yaml = ruamel.yaml.YAML()
        try:
            with open(f"{tmpdir}/charts/services/{app}/values-{project}.yaml") as opened_file:
                data = yaml.load(opened_file)
                if data["image"]["tag"] == tag:
                    log.warning(f"Tag already set, {tag}")
                    return
                else:
                    data["image"]["tag"] = tag
            with open(f"{tmpdir}/charts/services/{app}/values-{project}.yaml", "w") as opened_file:
                yaml.dump(data, opened_file)
                repo.index.add([f"{tmpdir}/charts/services/{app}/values-{project}.yaml"])
                repo.index.commit(f"update {tag}/{project}-{app}")
                repo.remotes.upstream.push()
            log.info(f"{project}-{app} was updated, ArgoCD will deploy soon")
            asyncio.run(send_slack(app, project, tag, user))
        except FileNotFoundError as e:
            log.error(e)
        else:
            return {"project": project, "app": app, "tag": tag, "result": "success"}


async def init():
    log.info(f"Auto Updater Waking Up...")
    start_time = time.time()
    log.info(f"Creating a Bundle of Apps...")
    projects = await asyncio.create_task(argocd.list_projects())
    log.info(f"{projects}")
    apps = [asyncio.create_task(argocd.list_apps(project)) for project in projects]
    bundle = filter(None, await asyncio.gather(*apps))
    auto_deploy = [asyncio.create_task(argocd.get_tag(apps, app)) for env in bundle
                   for apps in env for app in env[apps]]
    candidates = await asyncio.gather(*auto_deploy)
    log.warning(f"The following apps are eligible for Auto Deploy")
    log.info(f"{candidates}")
    updates = [asyncio.create_task(latest_image(i)) for i in candidates if i]
    await asyncio.gather(*updates)
    log.info("Task Completed in %.3f seconds" % (time.time() - start_time))
    log.info(f"Auto Updater Sleeping...")
