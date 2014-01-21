from mock import Mock, MagicMock, patch


@patch.multiple('clldfabric.util',
                time=Mock(),
                getpass=Mock(return_value='password'),
                confirm=Mock(return_value=True),
                exists=Mock(return_value=True),
                virtualenv=MagicMock(),
                sudo=Mock(),
                run=Mock(return_value='{"status": "ok"}'),
                local=Mock(),
                put=Mock(),
                env=MagicMock(),
                service=Mock(),
                cd=MagicMock(),
                require=Mock(),
                postgres=Mock())
def test_deploy():
    from clldfabric.util import deploy
    from clldfabric.config import App

    app = App('test', 9999, domain='d')
    assert app.src
    deploy(app, 'test', with_files=False)
    deploy(app, 'test', with_alembic=True, with_files=False)
    deploy(app, 'production', with_files=False)


@patch.multiple('clldfabric.tasks', execute=Mock())
def test_tasks():
    from clldfabric.tasks import (
        init, deploy, start, stop, maintenance, cache, uncache, run_script,
        create_downloads, copy_files, uninstall,
    )

    init('apics')
    deploy('test')
    stop('test')
    start('test')
    maintenance('test')
    cache()
    uncache()
    run_script('test', 'script')
    create_downloads('test')
    copy_files('test')
    uninstall('test')
