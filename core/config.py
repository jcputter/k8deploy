import os

from pydantic import BaseSettings


class Settings(BaseSettings):
    auto_update: bool = os.environ.get("AUTO_UPDATE")
    aws_region: str = os.environ.get("AWS_DEFAULT_REGION")
    git_repo: str = os.environ.get("GIT_REPO")
    work_dir: str = os.environ.get("WORK_DIR")
    argocd_base_url: str = os.environ.get("ARGOCD_BASE_URL")
    argocd_auth_header: dict = {
        'Authorization': 'Bearer ' + str(os.environ.get("ARGOCD_TOKEN"))}
    ignored_projects: list = ["default", "tools"]
    auto_update_interval: int = os.environ.get("AUTO_UPDATE_INTERVAL")
    github_token: str = os.environ.get("GITHUB_TOKEN")
    slack_enable: str = os.environ.get("SLACK_ENABLE")
    slack_webhook: str = os.environ.get("SLACK_WEBHOOK")
    google_client_id: str = os.environ.get("GOOGLE_CLIENT_ID")
    google_client_secret: str = os.environ.get("GOOGLE_CLIENT_SECRET")
    google_openid_endpoint: str = os.environ.get("GOOGLE_OPENID_ENDPOINT")
    fastapi_app_key: str = os.environ.get("FASTAPI_APP_KEY")
    autodeploy_annotation: str = os.environ.get("AUTO_DEPLOY_ANNOTATION ")


settings = Settings()
