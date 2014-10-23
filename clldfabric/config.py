"""
Configuration of CLLD apps.

.. note::

    Some fabirc tasks require additional information like

    - ssh config
    - environment variables
"""
from pathlib import PurePosixPath as path


# access details for the following servers must be provided in a suitable ssh config.
SERVERS = ['cldbstest', 'clld1', 'clld3', 'clld2', 'cldbs', 'clld4']



def repos(name):
    """git URL for a CLLD repository on GitHub.
    """
    return 'git://github.com/clld/%s.git' % name


class App(object):
    """Object storing basic configuration information for an app.
    """
    def __init__(self, name, port, **kw):
        self.name = name
        self.port = port
        self.host = kw.get('host', '%s.clld.org' % name)

        kw.setdefault('workers', 5)
        kw.setdefault('deploy_duration', 1)
        kw.setdefault('production', SERVERS[0])
        kw.setdefault('test', SERVERS[1])
        for k, v in kw.items():
            setattr(self, k, v)
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


APPS = [(app.name, app) for app in [
    App('dogonlanguages',
        8903,
        domain='dogonlanguages.clld.org',
        test=SERVERS[5],
        production=SERVERS[5]),
    App('csd',
        8902,
        domain='csd.clld.org',
        test=SERVERS[2],
        production=SERVERS[5]),
    App('tsezacp',
        8901,
        domain='tsezacp.clld.org',
        test=SERVERS[1],
        production=SERVERS[2]),
    App('nts',
        8900,
        domain='nts.clld.org',
        production=SERVERS[4],
        test=SERVERS[3]),
    App('tsammalex',
        8899,
        domain='tsammalex.clld.org',
        production=SERVERS[4],
        test=SERVERS[3]),
    App('sails',
        8898,
        domain='sails.clld.org',
        production=SERVERS[4],
        test=SERVERS[3]),
    App('dictionaria',
        8897,
        domain='dictionaria.clld.org',
        production=SERVERS[4],
        test=SERVERS[3]),
    App('autotyp',
        8896,
        domain='autotyp.clld.org',
        production=SERVERS[3],
        test=SERVERS[4]),
    App('clldportal',
        8895,
        domain='portal.clld.org',
        production=SERVERS[4]),
    App('asjp',
        8894,
        domain='asjp.clld.org',
        test=SERVERS[2],
        production=SERVERS[5]),
    App('ids',
        8893,
        domain='ids.clld.org',
        test=SERVERS[0],
        production=SERVERS[5]),
    App('valpal',
        8892,
        test=SERVERS[2],
        production=SERVERS[3]),
    App('waab',
        8891,
        domain="afbo.info",
        test=SERVERS[0],
        production=SERVERS[2]),
    App('phoible',
        8890,
        domain='phoible.org',
        test=SERVERS[1],
        production=SERVERS[2]),
    App('glottologcurator',
        8889,
        test=SERVERS[1],
        workers=1,
        dependencies=['glottolog3']),
    App('wold2',
        8888,
        domain='wold.clld.org',
        test=SERVERS[0],
        production=SERVERS[1]),
    App('wals3',
        8887,
        domain='wals.info',
        workers=7,
        test=SERVERS[5],
        production=SERVERS[0],
        with_blog=True),
    App('apics',
        8886,
        domain='apics-online.info',
        test=SERVERS[0],
        production=SERVERS[1]),
    App('jcld',
        8884,
        test=SERVERS[0],
        production=SERVERS[4],
        _pages=True,
        domain='jcld.clld.org'),
    App('wow',
        8883,
        test=SERVERS[1]),
    App('ewave',
        8882,
        domain='ewave-atlas.org',
        test=SERVERS[1],
        production=SERVERS[2]),
    App('glottolog3',
        8881,
        domain='glottolog.org',
        deploy_duration=2,
        workers=5,
        test=SERVERS[1],
        production=SERVERS[0]),
    App('solr',
        8080),
]]

# some consistency checks: names and ports must be unique to make it possible to deploy
# each app on each server.
_names = [app.name for _, app in APPS]
_ports = [app.port for _, app in APPS]
assert len(_names) == len(set(_names))
assert len(_ports) == len(set(_ports))

APPS = dict(APPS)

ERROR_EMAIL = 'robert_forkel@eva.mpg.de'
