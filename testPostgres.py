import logging
import os
import psycopg2

logger = logging.getLogger(__name__)

logger.warning('\n\n\nin testPostgres.py\n\n\n')

DATABASE_URL = os.environ['DATABASE_URL']

logger.warning('DATABASE_URL:', DATABASE_URL)

conn = psycopg2.connect(DATABASE_URL, sslmode='require')

SQL1 = "CREATE TABLE test (id serial PRIMARY KEY, num integer, data varchar);"

with conn:
    logger.warning('conn:', conn)
    with conn.cursor() as curs:
        logger.warning('curs:', curs)
        curs.execute(SQL1)

conn.close()