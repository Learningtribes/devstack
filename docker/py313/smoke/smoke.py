import importlib.metadata as md
import os
import subprocess
import sys
import tempfile
import time
import uuid

failures = []
RUN = uuid.uuid4().hex[:8]
SMOKE_DB = "py313_smoke"


def step(name, fn):
    try:
        print("%-38s OK   %s" % (name, fn()))
    except Exception as exc:
        failures.append(name)
        print("%-38s FAIL %s: %s" % (name, type(exc).__name__, str(exc)[:200]))


def env(name, default=None):
    value = os.environ.get(name, default)
    if value is None:
        raise SystemExit("missing env %s (run make env)" % name)
    return value


MYSQL_USER = env("PY313_MYSQL_USER", "edxapp")
MYSQL_PASSWORD = env("PY313_MYSQL_PASSWORD")
MYSQL_ROOT_PASSWORD = env("PY313_MYSQL_ROOT_PASSWORD")
MONGO_USER = env("PY313_MONGO_USER", "edxapp")
MONGO_PASSWORD = env("PY313_MONGO_PASSWORD")
RMQ_USER = env("PY313_RABBITMQ_USER", "edxapp")
RMQ_PASSWORD = env("PY313_RABBITMQ_PASSWORD")

print("python", sys.version.split()[0], "run", RUN)
for pkg in ("mysqlclient", "pymongo", "mongoengine", "celery", "kombu", "amqp", "pymemcache",
            "redis", "valkey", "elasticsearch", "Django"):
    print("  %-14s %s" % (pkg, md.version(pkg)))


def check(condition, message):
    if not condition:
        raise AssertionError(message)


def mysql_admin(statements):
    import MySQLdb
    conn = MySQLdb.connect(host="mysql", user="root", passwd=MYSQL_ROOT_PASSWORD)
    try:
        cur = conn.cursor()
        for statement in statements:
            cur.execute(statement)
    finally:
        conn.close()


def mysql():
    import MySQLdb
    conn = MySQLdb.connect(host="mysql", user=MYSQL_USER, passwd=MYSQL_PASSWORD, db=SMOKE_DB, charset="utf8mb4")
    try:
        cur = conn.cursor()
        cur.execute("select version()")
        version = cur.fetchone()[0]
        check(version.startswith("8.4"), "unexpected server version %s" % version)
        cur.execute("create table t (v varchar(32) not null unique) default charset utf8mb4")
        cur.execute("insert into t (v) values (%s)", ("emoji \U0001F600",))
        conn.commit()
        cur.execute("select v from t")
        check(cur.fetchone()[0] == "emoji \U0001F600", "utf8mb4 round trip failed")
        cur.execute("select table_collation from information_schema.tables where table_schema=%s and table_name='t'",
                    (SMOKE_DB,))
        collation = cur.fetchone()[0]
        cur.execute("show session status like 'Ssl_cipher'")
        tls = cur.fetchone()[1] or "off"
        return version, collation, "tls=%s" % tls, MySQLdb.get_client_info()
    finally:
        conn.close()


def mongo():
    import gridfs
    import mongoengine
    import pymongo
    from pymongo.errors import OperationFailure
    anonymous = pymongo.MongoClient("mongo", 27017, serverSelectionTimeoutMS=8000)
    try:
        anonymous[SMOKE_DB].t.insert_one({"x": 1})
        raise AssertionError("anonymous write succeeded, auth is not enforced")
    except OperationFailure:
        pass
    client = pymongo.MongoClient("mongo", 27017, username=MONGO_USER, password=MONGO_PASSWORD,
                                 authSource="admin", serverSelectionTimeoutMS=8000)
    me_db = SMOKE_DB + "_me"
    try:
        db = client[SMOKE_DB]
        db.t.insert_one({"_id": 1, "a": "x"})
        agg = list(db.t.aggregate([{"$group": {"_id": None, "n": {"$sum": 1}}}]))
        check(agg == [{"_id": None, "n": 1}], "aggregate returned %r" % agg)
        db.t.create_index("a", unique=True)
        check("a_1" in db.t.index_information(), "index missing")
        fs = gridfs.GridFS(db)
        check(fs.get(fs.put(b"hello")).read() == b"hello", "gridfs round trip failed")
        mongoengine.disconnect_all()
        mongoengine.connect(me_db, host="mongo", port=27017, username=MONGO_USER, password=MONGO_PASSWORD,
                            authentication_source="admin")

        class Item(mongoengine.Document):
            name = mongoengine.StringField()
            meta = {"collection": "items"}

        Item(name="a").save()
        check(Item.objects.count() == 1, "mongoengine count mismatch")
        return client.server_info()["version"], "auth=on", "agg/index/gridfs/mongoengine ok"
    finally:
        mongoengine.disconnect_all()
        client.drop_database(SMOKE_DB)
        client.drop_database(me_db)


def rabbitmq_and_celery():
    import kombu
    url = "amqp://%s:%s@rabbitmq:5672//" % (RMQ_USER, RMQ_PASSWORD)
    plain_queue = "py313_smoke_%s" % RUN
    celery_queue = "py313_smoke_celery_%s" % RUN
    workdir = tempfile.mkdtemp()
    log_path = os.path.join(workdir, "worker.log")
    with open(os.path.join(workdir, "smoke_tasks.py"), "w") as fh:
        fh.write(
            "import os\nfrom celery import Celery\n"
            "app = Celery('smoke_tasks', broker=os.environ['SMOKE_BROKER'], backend='rpc://')\n"
            "app.conf.task_default_queue = os.environ['SMOKE_QUEUE']\n"
            "@app.task\ndef add(a, b):\n    return a + b\n"
        )
    child_env = dict(os.environ, SMOKE_BROKER=url, SMOKE_QUEUE=celery_queue, PYTHONPATH=workdir)
    worker = None
    try:
        with kombu.Connection(url) as conn:
            queue = kombu.Queue(plain_queue, routing_key=plain_queue)
            conn.Producer().publish({"n": 1}, routing_key=plain_queue, declare=[queue])
            got = []
            with conn.Consumer(queue, callbacks=[lambda body, msg: (got.append(body), msg.ack())]):
                conn.drain_events(timeout=10)
            check(got == [{"n": 1}], "kombu consumed %r" % got)
        with open(log_path, "w") as log:
            worker = subprocess.Popen([sys.executable, "-m", "celery", "-A", "smoke_tasks", "worker", "-c", "1"],
                                      cwd=workdir, env=child_env, stdout=log, stderr=subprocess.STDOUT)
        os.environ.update(SMOKE_BROKER=url, SMOKE_QUEUE=celery_queue)
        sys.path.insert(0, workdir)
        import smoke_tasks
        deadline = time.time() + 40
        while not smoke_tasks.app.control.ping(timeout=2):
            check(worker.poll() is None and time.time() < deadline, "worker not ready")
        result = smoke_tasks.add.delay(2, 3).get(timeout=20)
        check(result == 5, "celery result %r" % result)
        return got, result
    except Exception:
        if os.path.exists(log_path):
            print("--- worker log tail ---")
            print("".join(open(log_path).readlines()[-15:]))
        raise
    finally:
        if worker:
            worker.terminate()
            worker.wait(timeout=20)
        with kombu.Connection(url) as conn:
            for name in (plain_queue, celery_queue):
                kombu.Queue(name)(conn.default_channel).delete(if_unused=False, if_empty=False)


def memcached():
    from pymemcache.client.base import Client
    client = Client("memcached:11211")
    key = "smoke_%s" % RUN
    client.set(key, b"v", expire=5)
    value = client.get(key)
    check(value == b"v", "memcached returned %r" % value)
    client.delete(key)
    return value


def valkey():
    import redis
    import valkey as valkey_py
    pair = redis.Redis("valkey").ping(), valkey_py.Valkey("valkey").ping()
    check(pair == (True, True), "ping returned %r" % (pair,))
    return pair


def elasticsearch():
    from elasticsearch import Elasticsearch
    es = Elasticsearch("http://elasticsearch:9200")
    alias = "py313_smoke_alias_%s" % RUN
    v1, v2 = alias + "_v1", alias + "_v2"
    try:
        es.indices.create(index=v1)
        es.indices.put_alias(index=v1, name=alias)
        es.index(index=v1, id=1, document={"t": "hello"}, refresh=True)
        hits = es.search(index=alias, query={"match": {"t": "hello"}})["hits"]["total"]["value"]
        check(hits == 1, "search via alias returned %d hits" % hits)
        es.indices.create(index=v2)
        es.indices.update_aliases(actions=[{"remove": {"index": v1, "alias": alias}},
                                           {"add": {"index": v2, "alias": alias}}])
        check(list(es.indices.get_alias(name=alias)) == [v2], "alias swap failed")
        return es.info()["version"]["number"], "alias swap ok"
    finally:
        es.options(ignore_status=404).indices.delete(index=[v1, v2])


def django_backends():
    import django
    from django.conf import settings
    settings.configure(
        DATABASES={"default": {"ENGINE": "django.db.backends.mysql", "NAME": SMOKE_DB, "USER": MYSQL_USER,
                               "PASSWORD": MYSQL_PASSWORD, "HOST": "mysql", "OPTIONS": {"charset": "utf8mb4"}}},
        CACHES={"mc": {"BACKEND": "django.core.cache.backends.memcached.PyMemcacheCache", "LOCATION": "memcached:11211"},
                "vk": {"BACKEND": "django.core.cache.backends.redis.RedisCache", "LOCATION": "redis://valkey:6379"}},
        INSTALLED_APPS=["django.contrib.auth", "django.contrib.contenttypes", "django.contrib.sessions"],
        USE_TZ=True,
    )
    django.setup()
    from django.core.cache import caches
    from django.core.management import call_command
    from django.db import connection
    call_command("migrate", verbosity=0)
    key = "smoke_%s" % RUN
    for alias in ("mc", "vk"):
        caches[alias].set(key, 1)
        check(caches[alias].get(key) == 1, "%s cache round trip failed" % alias)
        caches[alias].delete(key)
    check(connection.mysql_version >= (8, 0, 11), "mysql_version %r" % (connection.mysql_version,))
    return connection.mysql_version, "migrate + caches ok"


def native_imports():
    import ldap
    import lxml.etree
    import numpy
    import PIL
    import sass
    import scipy
    import shapely
    import yaml
    from cryptography.hazmat.backends import default_backend
    default_backend()
    return {m.__name__: getattr(m, "__version__", "?") for m in (ldap, numpy, scipy, PIL, sass, shapely, yaml)}


mysql_admin(["drop database if exists %s" % SMOKE_DB,
             "create database %s character set utf8mb4" % SMOKE_DB,
             "grant all on %s.* to '%s'@'%%'" % (SMOKE_DB, MYSQL_USER)])
try:
    step("mysqlclient -> MySQL 8.4", mysql)
    step("pymongo/mongoengine -> MongoDB 8.0", mongo)
    step("kombu + celery -> RabbitMQ 4.3", rabbitmq_and_celery)
    step("pymemcache -> Memcached 1.6", memcached)
    step("redis-py/valkey-py -> Valkey 8.1", valkey)
    step("elasticsearch-py -> ES 8.19", elasticsearch)
    step("Django 5.2 backends", django_backends)
    step("native extension imports", native_imports)
finally:
    mysql_admin(["drop database if exists %s" % SMOKE_DB])

if failures:
    print("\nFAILED: %s" % ", ".join(failures))
    sys.exit(1)
print("\nall smoke steps passed")
