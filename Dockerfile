FROM registry.access.redhat.com/ubi8/ubi-minimal:latest

USER root

ENV APP_ROOT=/opt/app-root/src
WORKDIR $APP_ROOT

RUN (microdnf module enable -y postgresql:16 || curl -o /etc/yum.repos.d/postgresql.repo $pgRepo) && \
    microdnf module enable python39:3.9 && \
    microdnf upgrade -y && \
    microdnf install --setopt=tsflags=nodocs -y postgresql python39 rsync tar procps-ng make && \
    rpm -qa | sort > packages-before-devel-install.txt && \
    microdnf install --setopt=tsflags=nodocs -y libpq-devel python39-devel gcc && \
    rpm -qa | sort > packages-after-devel-install.txt


COPY replication_subscription_runner.py replication_subscription_runner.py
COPY run_command.sh run_command.sh

RUN python3 -m pip install --upgrade pip setuptools wheel && \
    python3 -m pip install pipenv && \
    python3 -m pip install dumb-init && \
    pipenv install --system --dev

# remove devel packages that were only necessary for psycopg2 to compile
RUN microdnf remove -y $( comm -13 packages-before-devel-install.txt packages-after-devel-install.txt ) python39-setuptools && \
    rm packages-before-devel-install.txt packages-after-devel-install.txt && \
    microdnf clean all

# create a symlink to the library missing from postgresql:16.  This may not be needed in future.
RUN ln -s /usr/lib64/libpq.so.private16-5.16 /usr/lib64/libpq.so.5

USER 1001

ENTRYPOINT [ "dumb-init", "./run_command.sh" ]
