"""
Configuration of CLLD apps.

.. note::

    Some fabric tasks require additional information like

    - ssh config
    - environment variables
"""

import os
from six.moves.configparser import SafeConfigParser
from pathlib import PurePosixPath as path

# access details for the following servers must be provided in a suitable ssh config.
SERVERS = {'harald', 'uri', 'steve', 'clld2', 'christfried', 'matthew'}


class App(object):
    """Object storing basic configuration information for an app.
    """
    def __init__(self, name, port, **kw):
        self.name = name
        self.port = port
        self.host = kw.get('host', '%s.clld.org' % name)

        for k, v in kw.items():
            setattr(self, k, v)

        assert self.test in SERVERS
        assert self.production in SERVERS
        #assert self.production != self.test

    @property
    def src(self):
        """directory containing a clone of the app's source repository.
        """
        return self.venv.joinpath('src', self.name)

    @property
    def venv(self):
        """directory containing virtualenvs for clld apps.
        """
        return path('/usr/venvs').joinpath(self.name)

    @property
    def home(self):
        """home directory of the user running the app.
        """
        return path('/home').joinpath(self.name)

    @property
    def pages(self):
        """directory containing a clone of the app's pages repository.
        """
        if getattr(self, '_pages', False):
            return self.home.joinpath('%s-pages' % self.name)

    @property
    def newrelic_log(self):
        """path of the newrelic logfile.
        """
        return self.home.joinpath('newrelic.log')

    @property
    def www(self):
        return self.home.joinpath('www')

    @property
    def config(self):
        """path of the app's config file.
        """
        return self.home.joinpath('config.ini')

    @property
    def newrelic_config(self):
        """path of the app's newrelic config file.
        """
        return self.home.joinpath('newrelic.ini')

    @property
    def logs(self):
        """directory containing the app's logfiles.
        """
        return path('/var/log').joinpath(self.name)

    @property
    def error_log(self):
        return self.logs.joinpath('error.log')

    def bin(self, command):
        """bin directory of the app's virtualenv.
        """
        return str(self.venv.joinpath('bin', command))

    @property
    def supervisor(self):
        return path('/etc/supervisor/conf.d').joinpath('%s.conf' % self.name)

    @property
    def nginx_location(self):
        return path('/etc/nginx/locations.d').joinpath('%s.conf' % self.name)

    @property
    def nginx_htpasswd(self):
        return path('/etc/nginx/locations.d').joinpath('%s.htpasswd' % self.name)

    @property
    def nginx_site(self):
        return path('/etc/nginx/sites-enabled').joinpath(self.name)

    @property
    def sqlalchemy_url(self):
        return 'postgresql://{0}@/{0}'.format(self.name)


class Config(dict):

    _filename = 'apps.ini'

    _getters = {
        'getint': ['workers', 'deploy_duration', 'port'],
        'getboolean': ['with_blog', '_pages', 'pg_collkey'],
        'getlist': ['dependencies'],  # whitespace separated list
        'getlines': ['require_deb', 'require_pip'],  # newline separated list
    }

    def __init__(self):
        here = os.path.dirname(__file__)
        self.filename = os.path.join(here, self._filename)

        parser = SafeConfigParser()
        parser.getlist = lambda s, o: parser.get(s, o).split()
        parser.getlines = lambda s, o: [l.strip() for l in parser.get(s, o).splitlines() if l.strip()]
        found = parser.read(self.filename)
        if not found:
            raise RuntimeError('failed to read app config %r' % self.filename)

        getters = {}
        for attr, options in self._getters.items():
            getters.update(dict.fromkeys(options, getattr(parser, attr)))

        def items(section):
            for o in parser.options(section):
                yield o, getters.get(o, parser.get)(section, o)

        kwargs = [dict([('name', section)] + list(items(section)))
            for section in parser.sections()]
        apps = [App(**kw) for kw in kwargs]

        # some consistency checks: names and ports must be unique to make it
        # possible to deploy each app on each server.
        names = [app.name for app in apps]
        ports = [app.port for app in apps]
        assert len(names) == len(set(names))
        assert len(ports) == len(set(ports))

        super(Config, self).__init__((app.name, app) for app in apps)


APPS = Config()
