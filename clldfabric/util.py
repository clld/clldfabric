"""Deployment utilities for clld apps."""
# flake8: noqa
import time
import json
from getpass import getpass
import os
from datetime import datetime, timedelta
from importlib import import_module
import contextlib

from pytz import timezone, utc

from fabric.api import sudo, run, local, put, env, cd, task, execute, settings
from fabric.contrib.console import confirm
from fabric.contrib.files import exists
from fabtools import require
from fabtools.files import upload_template
from fabtools.python import virtualenv
from fabtools import service
from fabtools import postgres
from clldutils.path import Path

from clld.scripts.util import data_file

# we prevent the tasks defined here from showing up in fab --list, because we only
# want the wrapped version imported from clldfabric.tasks to be listed.
__all__ = []

TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), 'templates')

env.use_ssh_config = True


def get_input(prompt):
    return raw_input(prompt)


@contextlib.contextmanager
def working_directory(path):
    """A context manager which changes the working directory to the given
    path, and then changes it back to its previous value on exit.
    """
    prev_cwd = os.getcwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(prev_cwd)


def upload_template_as_root(dest, template, context=None, mode=None, owner='root'):
    if mode is not None:
        mode = int(mode, 8)
    upload_template(template, str(dest), context, use_jinja=True,
                    template_dir=TEMPLATE_DIR, use_sudo=True, backup=False,
                    mode=mode, chown=True, user=owner)


def create_file_as_root(path, content, **kw):
    kw.setdefault('owner', 'root')
    kw.setdefault('group', 'root')
    require.files.file(str(path), contents=content, use_sudo=True, **kw)


def get_template_variables(app, monitor_mode=False, with_blog=False):
    if monitor_mode and not os.environ.get('NEWRELIC_API_KEY'):
        print('--> Warning: no newrelic api key found in environment')  # pragma: no cover

    res = dict(
        app=app,
        env=env,
        newrelic_api_key=os.environ.get('NEWRELIC_API_KEY'),
        gunicorn=app.bin('gunicorn_paster'),
        newrelic=app.bin('newrelic-admin'),
        monitor_mode=monitor_mode,
        auth='',
        bloghost='',
        bloguser='',
        blogpassword='')

    if with_blog:  # pragma: no cover
        for key, default in [
            ('bloghost', 'blog.%s' % app.domain),
            ('bloguser', app.name),
            ('blogpassword', ''),
        ]:
            res[key] = os.environ.get(('%s_%s' % (app.name, key)).upper(), '')
            if not res[key]:
                custom = get_input('Blog %s [%s]: ' % (key[4:], default))
                res[key] = custom if custom else default
        assert res['blogpassword']

    return res


@task
def supervisor(app, command, template_variables=None):
    """
    .. seealso: http://serverfault.com/a/479754
    """
    template_variables = template_variables or get_template_variables(app)
    template_variables['PAUSE'] = {'pause': True, 'run': False}[command]
    upload_template_as_root(
        app.supervisor, 'supervisor.conf', template_variables, mode='644')
    if command == 'run':
        sudo('supervisorctl reread')
        sudo('supervisorctl update %s' % app.name)
        sudo('supervisorctl restart %s' % app.name)
    else:
        sudo('supervisorctl stop %s' % app.name)
        #sudo('supervisorctl reread %s' % app.name)
        #sudo('supervisorctl update %s' % app.name)
    time.sleep(1)


def require_bibutils(app):  # pragma: no cover
    """
    tar -xzvf bibutils_5.0_src.tgz -C /home/{app.name}
    cd /home/{app.name}/bibutils_5.0
    configure
    make
    sudo make install
    """
    if not exists('/usr/local/bin/bib2xml'):
        tgz = str(app.venv.joinpath('src', 'clld', 'tools', 'bibutils_5.0_src.tgz'))
        sudo('tar -xzvf {tgz} -C {app.home}'.format(tgz=tgz, app=app))
        with cd(str(app.home.joinpath('bibutils_5.0'))):
            sudo('./configure')
            sudo('make')
            sudo('make install')


@task
def uninstall(app):  # pragma: no cover
    for file_ in [app.supervisor, app.nginx_location, app.nginx_site]:
        file_ = str(file_)
        if exists(file_):
            sudo('rm %s' % file_)
    service.reload('nginx')
    sudo('supervisorctl stop %s' % app.name)


@task
def maintenance(app, hours=2, template_variables=None):
    """turn maintenance mode on|off
    """
    template_variables = template_variables or get_template_variables(app)
    ts = utc.localize(datetime.utcnow() + timedelta(hours=hours))
    ts = ts.astimezone(timezone('Europe/Berlin')).strftime('%Y-%m-%d %H:%M %Z%z')
    template_variables['timestamp'] = ts
    require.files.directory(str(app.www), use_sudo=True)
    upload_template_as_root(
        app.www.joinpath('503.html'), '503.html', template_variables)


def http_auth(app):
    pwds = {
        app.name: getpass(prompt='HTTP Basic Auth password for user %s: ' % app.name),
        'admin': ''}

    while not pwds['admin']:
        pwds['admin'] = getpass(prompt='HTTP Basic Auth password for user admin: ')

    for i, pair in enumerate([(n, p) for n, p in pwds.items() if p]):
        opts = 'bd'
        if i == 0:
            opts += 'c'
        sudo('htpasswd -%s %s %s %s' % (opts, app.nginx_htpasswd, pair[0], pair[1]))

    return bool(pwds[app.name]), """\
        proxy_set_header Authorization $http_authorization;
        proxy_pass_header  Authorization;
        auth_basic "%s";
        auth_basic_user_file %s;""" % (app.name, app.nginx_htpasswd)


@task
def copy_files(app):
    data_dir = data_file(import_module(app.name))
    tarball = '/tmp/%s-files.tgz' % app.name
    local('tar -C %s -czf %s files' % (data_dir, tarball))
    require.files.file(tarball, source=tarball)
    if os.path.exists(tarball):
        os.remove(tarball)  # pragma: no cover
    with cd('/tmp'):
        tarfile = tarball.split('/')[2]
        sudo('tar -xzf %s' % tarfile)
        target = app.www.joinpath('files')
        if exists(target):
            sudo('cp -ru files/* %s' % target)
            sudo('rm -rf files')
        else:
            sudo('mv files %s' % app.www)  # pragma: no cover
        sudo('chown -R root:root %s' % target)
        sudo('rm %s' % tarfile)
        sudo('tree %s' % app.www)


@task
def copy_rdfdump(app):
    execute(copy_downloads(app, pattern='*.n3.gz'))


@task
def copy_downloads(app, pattern='*'):
    dl_dir = app.src.joinpath(app.name, 'static', 'download')
    require.files.directory(dl_dir, use_sudo=True, mode="777")
    local_dl_dir = Path(import_module(app.name).__file__).parent.joinpath('static', 'download')
    for f in local_dl_dir.glob(pattern):
        target = dl_dir.joinpath(f.name)
        create_file_as_root(target, open(f.as_posix()).read())
        sudo('chown %s:%s %s' % (app.name, app.name, target))
    require.files.directory(dl_dir, use_sudo=True, mode="755")


def init_pg_collkey(app):
    require.files.file(
        '/tmp/collkey_icu.sql',
        source=os.path.join(
            os.path.dirname(__file__), 'pg_collkey-v0.5', 'collkey_icu.sql'))
    sudo('sudo -u postgres psql -f /tmp/collkey_icu.sql -d {0.name}'.format(app))


@task
def deploy(app, environment, with_alembic=False, with_blog=False, with_files=True):
    with settings(warn_only=True):
        lsb_release = run('lsb_release -a')
    for codename in ['trusty', 'precise']:
        if codename in lsb_release:
            lsb_release = codename
            break
    else:
        if lsb_release != '{"status": "ok"}':
            # if this were the case, we'd be in a test!
            raise ValueError('unsupported platform: %s' % lsb_release)

    if environment == 'test' and app.workers > 3:
        app.workers = 3

    template_variables = get_template_variables(
        app,
        monitor_mode='true' if environment == 'production' else 'false',
        with_blog=with_blog)

    require.users.user(app.name, shell='/bin/bash')
    require.postfix.server(env['host'])
    require.postgres.server()
    require.deb.packages(app.require_deb)
    require.postgres.user(app.name, app.name)
    require.postgres.database(app.name, app.name)
    require.files.directory(str(app.venv), use_sudo=True)

    if getattr(app, 'pg_unaccent', False):
        require.deb.packages(['postgresql-contrib'])
        sudo('sudo -u postgres psql -c "{0}" -d {1.name}'.format(
            'CREATE EXTENSION IF NOT EXISTS unaccent WITH SCHEMA public;',
            app))    

    with_pg_collkey = getattr(app, 'pg_collkey', False)
    if with_pg_collkey:
        pg_version = '9.1' if lsb_release == 'precise' else '9.3'
        if not exists('/usr/lib/postgresql/%s/lib/collkey_icu.so' % pg_version):
            require.deb.packages(['postgresql-server-dev-%s' % pg_version, 'libicu-dev'])
            upload_template_as_root(
                '/tmp/Makefile', 'pg_collkey_Makefile', dict(pg_version=pg_version))

            require.files.file(
                '/tmp/collkey_icu.c',
                source=os.path.join(
                    os.path.dirname(__file__), 'pg_collkey-v0.5', 'collkey_icu.c'))
            with cd('/tmp'):
                sudo('make')
                sudo('make install')
        init_pg_collkey(app)

    if lsb_release == 'precise':
        require.deb.package('python-dev')
        require.python.virtualenv(str(app.venv), use_sudo=True)
    else:
        require.deb.package('python3-dev')
        require.deb.package('python-virtualenv')
        if not exists(str(app.venv.joinpath('bin'))):
            sudo('virtualenv -q --python=python3 %s' % app.venv)

    require.files.directory(str(app.logs), use_sudo=True)

    if app.pages and not exists(str(app.pages)):
        with cd(str(app.home)):
            sudo('sudo -u {0} git clone https://github.com/clld/{0}-pages.git'.format(app.name))

    with virtualenv(str(app.venv)):
        require.python.pip('6.0.6')
        sp = env['sudo_prefix']
        env['sudo_prefix'] += ' -H'  # set HOME for pip log/cache
        require.python.packages(app.require_pip, use_sudo=True)
        for name in [app.name] + getattr(app, 'dependencies', []):
            pkg = '-e git+git://github.com/clld/%s.git#egg=%s' % (name, name)
            require.python.package(pkg, use_sudo=True)
        env['sudo_prefix'] = sp
        sudo('webassets -m %s.assets build' % app.name)
        res = sudo('python -c "import clld; print(clld.__file__)"')
        assert res.startswith('/usr/venvs') and '__init__.py' in res
        template_variables['clld_dir'] = '/'.join(res.split('/')[:-1])

    require_bibutils(app)

    #
    # configure nginx:
    #
    require.files.directory(
        os.path.dirname(str(app.nginx_location)),
        owner='root', group='root', use_sudo=True)

    restricted, auth = http_auth(app)
    if restricted:
        template_variables['auth'] = auth
    template_variables['admin_auth'] = auth

    if environment == 'test':
        upload_template_as_root('/etc/nginx/sites-available/default', 'nginx-default.conf')
        template_variables['SITE'] = False
        upload_template_as_root(
            app.nginx_location, 'nginx-app.conf', template_variables)
    elif environment == 'production':
        template_variables['SITE'] = True
        upload_template_as_root(app.nginx_site, 'nginx-app.conf', template_variables)
        upload_template_as_root(
            '/etc/logrotate.d/{0}'.format(app.name), 'logrotate.conf', template_variables)

    maintenance(app, hours=app.deploy_duration, template_variables=template_variables)
    service.reload('nginx')

    #
    # TODO: replace with initialization of db from data repos!
    #
    if with_files:
        if confirm('Copy files?', default=False):
            execute(copy_files, app)

    if not with_alembic and confirm('Recreate database?', default=False):
        db_name = get_input('from db [{0.name}]: '.format(app))
        local('pg_dump -x -O -f /tmp/{0.name}.sql {1}'.format(app, db_name or app.name))
        local('gzip -f /tmp/{0.name}.sql'.format(app))
        require.files.file(
            '/tmp/{0.name}.sql.gz'.format(app),
            source="/tmp/{0.name}.sql.gz".format(app))
        sudo('gunzip -f /tmp/{0.name}.sql.gz'.format(app))
        supervisor(app, 'pause', template_variables)

        if postgres.database_exists(app.name):
            with cd('/var/lib/postgresql'):
                sudo('sudo -u postgres dropdb %s' % app.name)

            require.postgres.database(app.name, app.name)
            if with_pg_collkey:
                init_pg_collkey(app)

        sudo('sudo -u {0.name} psql -f /tmp/{0.name}.sql -d {0.name}'.format(app))
    else:
        if exists(app.src.joinpath('alembic.ini')):
            if confirm('Upgrade database?', default=False):
                # Note: stopping the app is not strictly necessary, because the alembic
                # revisions run in separate transactions!
                supervisor(app, 'pause', template_variables)
                with virtualenv(str(app.venv)):
                    with cd(str(app.src)):
                        sudo('sudo -u {0.name} {1} -n production upgrade head'.format(
                            app, app.bin('alembic')))

                if confirm('Vacuum database?', default=False):
                    if confirm('VACUUM FULL?', default=False):
                        sudo('sudo -u postgres vacuumdb -f -z -d %s' % app.name)
                    else:
                        sudo('sudo -u postgres vacuumdb -z -d %s' % app.name)

    template_variables['TEST'] = {'test': True, 'production': False}[environment]
    # We only set add a setting clld.files, if the corresponding directory exists;
    # otherwise the app would throw an error on startup.
    template_variables['files'] = False
    if exists(app.www.joinpath('files')):
        template_variables['files'] = app.www.joinpath('files')
    upload_template_as_root(app.config, 'config.ini', template_variables)
    upload_template_as_root(app.newrelic_config, 'newrelic.ini', template_variables)

    supervisor(app, 'run', template_variables)

    time.sleep(5)
    res = run('curl http://localhost:%s/_ping' % app.port)
    assert json.loads(res)['status'] == 'ok'


@task
def pipfreeze(app, environment):
    with virtualenv(app.venv):
        with open('requirements.txt', 'w') as fp:
            for line in sudo('pip freeze').splitlines():
                if '%s.git' % app.name in line:
                    continue
                if line.split('==')[0].lower() in ['fabric', 'pyx', 'fabtools', 'paramiko', 'pycrypto', 'babel']:
                    continue
                if 'clld.git' in line:
                    line = 'clld'
                if 'clldmpg.git' in line:
                    line = 'clldmpg'
                fp.write(line+ '\n')


@task
def run_script(app, script_name, *args):  # pragma: no cover
    with cd(str(app.home)):
        sudo(
            '%s %s %s#%s %s' % (
                app.bin('python'),
                app.src.joinpath(app.name, 'scripts', '%s.py' % script_name),
                os.path.basename(str(app.config)),
                app.name,
                ' '.join('%s' % arg for arg in args),
            ),
            user=app.name)


@task
def create_downloads(app):  # pragma: no cover
    dl_dir = app.src.joinpath(app.name, 'static', 'download')
    require.files.directory(dl_dir, use_sudo=True, mode="777")
    # run the script to create the exports from the database as glottolog3 user
    run_script(app, 'create_downloads')
    require.files.directory(dl_dir, use_sudo=True, mode="755")


def bootstrap(nr='y'):  # pragma: no cover
    for pkg in 'vim tree nginx open-vm-tools'.split():
        require.deb.package(pkg)

    sudo('/etc/init.d/nginx start')

    if nr == 'y':
        for cmd in [
            'wget -O /etc/apt/sources.list.d/newrelic.list http://download.newrelic.com/debian/newrelic.list',
            'apt-key adv --keyserver hkp://subkeys.pgp.net --recv-keys 548C16BF',
            'apt-get update',
            'apt-get install newrelic-sysmond',
            'nrsysmond-config --set license_key=%s' % os.environ['NEWRELIC_API_KEY'],
            '/etc/init.d/newrelic-sysmond start',
        ]:
            sudo(cmd)
