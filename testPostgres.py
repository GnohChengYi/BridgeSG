import os
import psycopg2

print('\n\n\nin testPostgres.py\n\n\n')

DATABASE_URL = os.environ['DATABASE_URL']

print('DATABASE_URL:', DATABASE_URL)

conn = psycopg2.connect(DATABASE_URL, sslmode='require')

SQL1 = "CREATE TABLE test (id serial PRIMARY KEY, num integer, data varchar);"

with conn:
    print('conn:', conn)
    with conn.cursor() as curs:
        print('curs:', curs)
        curs.execute(SQL1)

conn.close()