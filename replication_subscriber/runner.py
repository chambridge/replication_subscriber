#!/opt/app-root/bin/python
import logging
import os
import sys
from functools import partial

from atexit import register
from signal import SIGINT as CTRL_C_TERM
from signal import SIGTERM as OPENSHIFT_TERM
from signal import Signals
from signal import signal

from sqlalchemy import create_engine
from sqlalchemy import text as sa_text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.sql import exists
from sqlalchemy.sql import select

import app_common_python


__all__ = ("main", "run")

LOGGER_NAME = "replication-subscriber"
SSL_VERIFY_FULL = "verify-full"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)


class ShutdownHandler:
    def __init__(self):
        self._shutdown = False

    def _signal_handler(self, signum, frame):
        signame = Signals(signum).name
        logger.info("Gracefully Shutting Down. Received: %s", signame)
        self._shutdown = True

    def register(self):
        signal(OPENSHIFT_TERM, self._signal_handler)
        signal(CTRL_C_TERM, self._signal_handler)

    def shut_down(self):
        return self._shutdown


def register_shutdown(function, message):
    def atexit_function():
        logger.info(message)
        function()

    register(atexit_function)


def _init_config():
    db_uri = None
    cfg = app_common_python.LoadedConfig
    if cfg and cfg.database:
        db_user = cfg.database.username
        db_password = cfg.database.password
        db_host = cfg.database.hostname
        db_port = cfg.database.port
        db_name = cfg.database.name
        if cfg.database.rdsCa:
            db_ssl_cert = cfg.rds_ca()
        db_ssl_mode = os.getenv("DB_SSL_MODE", "")
        db_uri = f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
        if db_ssl_mode == SSL_VERIFY_FULL:
            db_uri += f"?sslmode={db_ssl_mode}&sslrootcert={db_ssl_cert}"
    return db_uri

def _init_db(db_uri):
    engine = create_engine(db_uri)
    return sessionmaker(bind=engine)


def _excepthook(logger, type, value, traceback):
    logger.exception("Replication subcription job failed", exc_info=value)


def check_or_create_hosts_tables(logger, session):
    if not exists(select(sa_text("table_name")).select_from("information_schema.tables").where("schema_name == 'hbi' AND table_name =='hosts'")):
        logger.info("hbi.hosts not found.")
        hosts_table_create = """CREATE TABLE hbi.hosts (
            id uuid NOT NULL,
            account character varying(10),
            display_name character varying(200),
            created_on timestamp with time zone NOT NULL,
            modified_on timestamp with time zone NOT NULL,
            facts jsonb,
            tags jsonb,
            canonical_facts jsonb NOT NULL,
            system_profile_facts jsonb,
            ansible_host character varying(255),
            stale_timestamp timestamp with time zone NOT NULL,
            reporter character varying(255) NOT NULL,
            per_reporter_staleness jsonb DEFAULT '{}'::jsonb NOT NULL,
            org_id character varying(36) NOT NULL,
            groups jsonb NOT NULL
        );"""
        session.execute(hosts_table_create)
        logger.info("hbi.hosts created.")


def check_or_create_schema(logger, session):
    if not exists(select(sa_text("schema_name")).select_from("information_schema.schemata").where("schema_name == 'hbi'")):
        logger.info("hbi schema not found.")
        session.execute("CREATE SCHEMA IF NOT EXISTS hbi")
        logger.info("hbi schema created.")
    check_or_create_hosts_tables(logger, session)


def check_or_create_subscription(logger, session):
    if exists(select(sa_text("subname")).select_from("pg_subscription").where("subname == 'hbi_hosts_sub'")):
        logger.debug("hbi_hosts_sub found.")
        return
    logger.info("hbi_hosts_sub not found.")
    hbi_file_list = [
            "/etc/db/hbi/db_host",
            "/etc/db/hbi/db_port",
            "/etc/db/hbi/db_name",
            "/etc/db/hbi/db_user",
            "/etc/db/hbi/db_password",
        ]
    if all(list(map(os.path.isfile, hbi_file_list))):
        logger.info("HBI secret files exist.")
        with open("/etc/db/hbi/db_host") as file:
            hbi_host = file.read().rstrip()
        with open("/etc/db/hbi/db_port") as file:
            hbi_port = file.read().rstrip()
        with open("/etc/db/hbi/db_name") as file:
            hbi_db_name = file.read().rstrip()
        with open("/etc/db/hbi/db_user") as file:
            hbi_user = file.read().rstrip()
        with open("/etc/db/hbi/db_password") as file:
            hbi_password = file.read().rstrip()
    hbi_publication = os.getenv("HBI_PUBLICATION", "hbi_hosts_pub")
    subscription_create = "CREATE SUBSCRIPTION hbi_hosts_sub CONNECTION 'host=" + hbi_host + " port=" + hbi_port + " user=" + hbi_user + " dbname=" + hbi_db_name + " password=" + hbi_password + "' PUBLICATION " +  hbi_publication+ ";"
    session.execute(subscription_create)
    logger.info("hbi_hosts_sub created.")

def run(logger, session):
    logger.info("Starting replication subcription runner")
    check_or_create_schema(logger, session)
    check_or_create_subscription(logger, session)
    check_or_create_subscription(logger, session)
    logger.info("Finishing replication subcription runner")


def main(logger):
    db_uri = _init_config()
    Session = _init_db(db_uri)
    session = Session()
    register_shutdown(session.get_bind().dispose, "Closing database")

    shutdown_handler = ShutdownHandler()
    shutdown_handler.register()
    run(logger, session)


if __name__ == "__main__":
    logger = logging.getLogger(f"{LOGGER_NAME}")
    sys.excepthook = partial(_excepthook, logger)

    main(logger)
