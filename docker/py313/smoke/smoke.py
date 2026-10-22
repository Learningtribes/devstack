import importlib.metadata as md
import os
import subprocess
import sys
import tempfile
import time

failures = []


def step(name, fn):
    try:
        print("%-38s OK   %s" % (name, fn()))
    except Exception as exc:
        failures.append(name)
        print("%-38s FAIL %s: %s" % (name, type(exc).__name__, str(exc)[:160]))


def env(name, default=None):
    value = os.environ.get(name, default)
    if value is None:
        raise SystemExit("missing env %s (run make env)" % name)
    return value


MYSQL_USER = env("PY313_MYSQL_USER", "edxapp")
MYSQL_PASSWORD = env("PY313_MYSQL_PASSWORD")
RMQ_USER = env("PY313_RABBITMQ_USER", "edxapp")
RMQ_PASSWORD = env("PY313_RABBITMQ_PASSWORD")

print("python", sys.version.split()[0])
for pkg in ("mysqlclient", "pymongo", "mongoengine", "celery", "kombu", "amqp", "pymemcache",
            "redis", "valkey", "elasticsearch", "Django"):
    print("  %-14s %s" % (pkg, md.version(pkg)))


def mysql():
    import MySQLdb
    conn = MySQLdb.connect(host="mysql", user=MYSQL_USER, passwd=MYSQL_PASSWORD, db="edxapp", charset="utf8mb4")
    cur = conn.cursor()
    cur.execute("select version(), @@collation_server")
    return cur.fetchone() + (MySQLdb.get_client_info(),)


def mongo():
    import gridfs
    import mongoengine
    import pymongo
    client = pymongo.MongoClient("mongo", 27017, serverSelectionTimeoutMS=8000)
    db = client.py313_smoke
    db.t.drop()
    db.t.insert_one({"_id": 1, "a": "x"})
    agg = list(db.t.aggregate([{"$group": {"_id": None, "n": {"$sum": 1}}}]))
    fs = gridfs.GridFS(db)
    data = fs.get(fs.put(b"hello")).read()
    mongoengine.connect("py313_smoke_me", host="mongo", port=27017)
    client.drop_database("py313_smoke")
    return client.server_info()["version"], agg, data


def rabbitmq_and_celery():
    import kombu
    url = "amqp://%s:%s@rabbitmq:5672//" % (RMQ_USER, RMQ_PASSWORD)
    with kombu.Connection(url) as conn:
        queue = kombu.Queue("py313_smoke", routing_key="py313_smoke")
        conn.Producer().publish({"n": 1}, routing_key="py313_smoke", declare=[queue])
        got = []
        with conn.Consumer(queue, callbacks=[lambda body, msg: (got.append(body), msg.ack())]):
            conn.drain_events(timeout=10)
    workdir = tempfile.mkdtemp()
    with open(os.path.join(workdir, "smoke_tasks.py"), "w") as fh:
        fh.write(
            "import os\nfrom celery import Celery\n"
            "app = Celery('smoke_tasks', broker=os.environ['SMOKE_BROKER'], backend='rpc://')\n"
            "@app.task\ndef add(a, b):\n    return a + b\n"
        )
    child_env = dict(os.environ, SMOKE_BROKER=url, PYTHONPATH=workdir)
    worker = subprocess.Popen([sys.executable, "-m", "celery", "-A", "smoke_tasks", "worker", "-c", "1"],
                              cwd=workdir, env=child_env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        time.sleep(12)
        sys.path.insert(0, workdir)
        os.environ["SMOKE_BROKER"] = url
        import smoke_tasks
        return got, smoke_tasks.add.delay(2, 3).get(timeout=20)
    finally:
        worker.terminate()


def memcached():
    from pymemcache.client.base import Client
    client = Client("memcached:11211")
    client.set("k", b"v", expire=5)
    return client.get("k")


def valkey():
    import redis
    import valkey as valkey_py
    return redis.Redis("valkey").ping(), valkey_py.Valkey("valkey").ping()


def elasticsearch():
    from elasticsearch import Elasticsearch
    es = Elasticsearch("http://elasticsearch:9200")
    es.index(index="py313_smoke", id=1, document={"t": "hello"}, refresh=True)
    hits = es.search(index="py313_smoke", query={"match": {"t": "hello"}})["hits"]["total"]["value"]
    es.indices.delete(index="py313_smoke")
    return es.info()["version"]["number"], hits


def django_backends():
    import django
    from django.conf import settings
    settings.configure(
        DATABASES={"default": {"ENGINE": "django.db.backends.mysql", "NAME": "edxapp", "USER": MYSQL_USER,
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
    caches["mc"].set("a", 1)
    caches["vk"].set("a", 1)
    return connection.mysql_version, caches["mc"].get("a"), caches["vk"].get("a")


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


step("mysqlclient -> MySQL 8.4", mysql)
step("pymongo/mongoengine -> MongoDB 8.0", mongo)
step("kombu + celery -> RabbitMQ 4.3", rabbitmq_and_celery)
step("pymemcache -> Memcached 1.6", memcached)
step("redis-py/valkey-py -> Valkey 8.1", valkey)
step("elasticsearch-py -> ES 8.19", elasticsearch)
step("Django 5.2 backends", django_backends)
step("native extension imports", native_imports)

if failures:
    print("\nFAILED: %s" % ", ".join(failures))
    sys.exit(1)
print("\nall smoke steps passed")
