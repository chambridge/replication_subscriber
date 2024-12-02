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

import app_common_python


__all__ = ("main", "run")

LOGGER_NAME = "replication-subscription-runner"
SSL_VERIFY_FULL = "verify-full"


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


def run(logger, session):
    logger.info("Starting replication subcription runner")

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
