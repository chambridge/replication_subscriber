#!/usr/bin/python
import os
import sys
from functools import partial

from sqlalchemy import create_engine
from sqlalchemy import text as sa_text
from sqlalchemy.orm import sessionmaker

__all__ = ("main", "run")

LOGGER_NAME = "replication-subscription-runner"


def _init_config():
    config = None
    return config


def _init_db(config):
    engine = create_engine(config.db_uri)
    return sessionmaker(bind=engine)


def _excepthook(logger, type, value, traceback):
    logger.exception("Replication subcription job failed", exc_info=value)


def run(logger, session):
    logger.info("Starting replication subcription runner")

    logger.info("Finishing replication subcription runner")


def main(logger):
    config = _init_config()
    Session = _init_db(config)
    session = Session()
    register_shutdown(session.get_bind().dispose, "Closing database")

    shutdown_handler = ShutdownHandler()
    shutdown_handler.register()
    run(logger, session)


if __name__ == "__main__":
    logger = get_logger(LOGGER_NAME)
    sys.excepthook = partial(_excepthook, logger)

    main(logger)
