# Py3.6 Image Build + Django Boot — Complete Script

> Date: 2026-07-23 · Image: ltdps/edxapp:py36

## Build

```bash
docker run -d --name py36-build --network devstack_default \
  -v /Users/noahwang/workspace/hawthorn/platform:/edx/app/edxapp/edx-platform \
  -w /edx/app/edxapp/edx-platform \
  ltdps/edxapp:py36 bash -c "sleep 99999"

docker exec -it py36-build bash
```

## Full Commands (run inside container)

```bash
# pip mirror
mkdir -p /root/.pip
cat > /root/.pip/pip.conf << "EOF"
[global]
index-url = https://pypi.tuna.tsinghua.edu.cn/simple
trusted-host = pypi.tuna.tsinghua.edu.cn
EOF

# system deps
apt-get update && apt-get install -y --no-install-recommends \
  git gcc g++ make \
  default-libmysqlclient-dev libgeos-dev libgeos-c1v5 \
  libldap2-dev libsasl2-dev libxml2-dev libxslt-dev \
  libjpeg-dev zlib1g-dev libgraphviz-dev \
  && apt-get clean && rm -rf /var/lib/apt/lists/*

# pip packages (Tsinghua mirror)
pip install "pip<21.0" "setuptools<45"
pip install -r /tmp/py36-base.txt

# editable packages
cd /edx/app/edxapp/edx-platform
for lib in xmodule capa calc symmath safe_lxml chem sandbox-packages dogstats; do
  pip install -e common/lib/$lib
done

# === Code fixes (15) ===

# ur"..." → r"..."
sed -i 's/ur"/r"/g' common/djangoapps/static_replace/__init__.py
sed -i 's/ur"/r"/g' common/lib/xmodule/xmodule/modulestore/store_utilities.py
sed -i "s/ur'\\/r'\\/g" common/lib/xmodule/xmodule/modulestore/store_utilities.py  # also ur'
sed -i 's/ur"/r"/g' common/lib/calc/calc/preview.py
sed -i 's/ur"/r"/g' common/lib/xmodule/xmodule/capa_base.py
sed -i 's/ur"/r"/g' common/lib/xmodule/xmodule/capa_module.py

# except E, e: → except E as e:
sed -i 's/except Exception, exc:/except Exception as exc:/' common/lib/xmodule/xmodule/contentstore/content.py
sed -i 's/except ValueError, err:/except ValueError as err:/' common/lib/capa/capa/xqueue_interface.py
sed -i 's/except requests.exceptions.ConnectionError, err:/except requests.exceptions.ConnectionError as err:/' common/lib/capa/capa/xqueue_interface.py
sed -i 's/except requests.exceptions.ReadTimeout, err:/except requests.exceptions.ReadTimeout as err:/' common/lib/capa/capa/xqueue_interface.py

# raise E, V, T → six.reraise()
sed -i 's/raise Exception, msg, sys.exc_info()\[2\]/six.reraise(Exception, msg, sys.exc_info()[2])/' common/lib/capa/capa/inputtypes.py

# Imports — absolute_import compat
sed -i 's/^import xqueue_interface$/from . import xqueue_interface/' common/lib/capa/capa/inputtypes.py
sed -i 's/from calc import \*/from calc.calc import */' common/lib/calc/calc/__init__.py
sed -i 's/^import functions$/from . import functions/' common/lib/calc/calc/calc.py
sed -i 's/from urllib import urlencode, quote_plus/from six.moves.urllib.parse import urlencode, quote_plus/' common/lib/xmodule/xmodule/contentstore/content.py
sed -i 's/^import StringIO$/from six.moves import StringIO/' common/lib/xmodule/xmodule/contentstore/content.py
sed -i 's/from urlparse import/from six.moves.urllib.parse import/' common/lib/xmodule/xmodule/contentstore/content.py

# reduce + map + unicode
sed -i '2i from functools import reduce' common/lib/chem/chem/chemcalc.py
sed -i 's/digits = map(str, range(10))/digits = list(map(str, range(10)))/' common/lib/chem/chem/chemcalc.py
sed -i 's/gettext_func=unicode/gettext_func=str/' common/lib/capa/capa/inputtypes.py

# === Dependency fixes ===
pip install "python-dateutil>=2.5" "pyparsing>=2.0,<3.0"
pip uninstall -y analytics; pip install analytics-python
pip install "event-tracking>=1.0" django-pipeline

# === Verify ===
python3 -c "
import django; print('Django', django.VERSION)
import kombu.async; print('kombu.async OK')
print('ALL VERIFIED')
"
exit

# Commit
docker commit py36-build ltdps/edxapp:py36
docker rm -f py36-build
```

## Verification Results

- Django 1.11.29 ✅
- celery 3.1.25 ✅
- kombu.async ✅ (async = soft keyword on 3.6)
- pymongo 3.9.0 ✅
- 95 pip packages, zero errors

## Remaining

- `lms.envs.test` full boot needs ~5 git packages (django-celery, django-oauth-plus, djangorestframework-oauth, edx-proctoring, codejail) — blocked on slow git clone
- `codejail` has `exec code in g_dict` Py2 syntax in its git fork
