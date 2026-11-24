# Build only from the exact CI-verified public controller bundle, never a checkout or secrets.
FROM debian:13-slim
RUN apt-get update -qq && apt-get install -y --no-install-recommends python3 python3-pil ca-certificates libssl3t64 zlib1g libstdc++6 && rm -rf /var/lib/apt/lists/* \
    && groupadd -g 10001 ipazake && useradd -u 10001 -g 10001 -d /var/lib/ipazake -s /usr/sbin/nologin ipazake \
    && install -d -m 0700 -o 10001 -g 10001 /var/lib/ipazake
WORKDIR /opt/ipazake
COPY bin/ bin/
COPY tools/ tools/
COPY SOURCE_COMMIT .
RUN chmod -R go-w /opt/ipazake && test -x bin/telegram-bot-api && test -x bin/delivery-crypt
ENV IPAZAKE_CREDENTIAL_MODE=environment IPAZAKE_STATE=/var/lib/ipazake HOME=/var/lib/ipazake PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 LAB_RUNTIME=vps
USER 10001:10001
STOPSIGNAL SIGTERM
ENTRYPOINT ["/usr/bin/python3", "/opt/ipazake/tools/telegram_daemon.py"]
