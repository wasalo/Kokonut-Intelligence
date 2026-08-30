FROM ubuntu:24.04
RUN apt-get update -qq \
    && apt-get install -y -qq curl ca-certificates gnupg git python3 python3-venv >/dev/null \
    && install -m 0755 -d /etc/apt/keyrings \
    && curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc \
    && chmod a+r /etc/apt/keyrings/docker.asc \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo $VERSION_CODENAME) stable" > /etc/apt/sources.list.d/docker.list \
    && apt-get update -qq \
    && apt-get install -y -qq docker-ce-cli docker-compose-plugin >/dev/null \
    && curl -fsSL https://github.com/getsops/sops/releases/download/v3.9.4/sops-v3.9.4.linux.amd64 -o /usr/local/bin/sops \
    && chmod +x /usr/local/bin/sops \
    && curl -fsSL https://github.com/FiloSottile/age/releases/download/v1.2.1/age-v1.2.1-linux-amd64.tar.gz \
    | tar xz -C /usr/local/bin --strip-components=1 age/age age/age-keygen \
    && git config --global --add safe.directory /opt/ki-staging \
    && rm -rf /var/lib/apt/lists/*
