FROM python:3.10.4-slim-bullseye
# docker build --build-arg SSH_KEY="$(cat ~/.ssh/id_rsa)" -t k8sdeploy .
ENV PYTHONUNBUFFERED=1
ARG SSH_KEY
ENV SLACK_ENABLE=True
ENV AUTO_UPDATE=True
ENV AUTO_UPDATE_INTERVAL=60
ENV AWS_DEFAULT_REGION=""
ENV GIT_REPO=""
ENV DEBIAN_FRONTEND=noninteractive
RUN apt update && apt install -y git ssh && rm -rf /var/lib/apt/lists/*
RUN mkdir ~/.ssh/
RUN echo "${SSH_KEY}" > ~/.ssh/id_rsa
RUN chmod 600 ~/.ssh/id_rsa
RUN ssh-keyscan github.com >> ~/.ssh/known_hosts
WORKDIR /usr/src/app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD [ "python", "./app.py" ]