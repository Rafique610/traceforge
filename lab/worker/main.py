"""Worker entrypoint: `python -m worker.main`."""

import logging
import signal

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from worker import handlers, heartbeat, queue
from worker.settings import get_settings

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s"
)
log = logging.getLogger("worker.main")


def main() -> None:
    settings = get_settings()
    running = True

    def stop(*_):
        nonlocal running
        running = False

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)

    engine = create_engine(
        settings.database_url, pool_size=settings.db_pool_size, pool_pre_ping=True
    )
    factory = sessionmaker(engine, expire_on_commit=False)
    client = queue.connect_with_retry(settings)
    log.info(
        "worker consuming %s on %s:%s",
        settings.order_queue,
        settings.redis_host,
        settings.redis_port,
    )
    while running:
        heartbeat.beat(client)
        queue.consume_once(
            client, settings, lambda job: handlers.confirm_order(factory, job)
        )


if __name__ == "__main__":
    main()
