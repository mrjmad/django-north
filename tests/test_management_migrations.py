import os

from django.core.exceptions import ImproperlyConfigured
from django.db import connection

import pytest

from django_north.management import migrations


def test_get_known_versions(settings):
    # wrong path
    message = "settings.NORTH_MIGRATIONS_ROOT is improperly configured."

    settings.NORTH_MIGRATIONS_ROOT = '/path/to/nowhere'
    with pytest.raises(ImproperlyConfigured, message=message):
        migrations.get_known_versions()

    root = os.path.dirname(__file__)
    settings.NORTH_MIGRATIONS_ROOT = os.path.join(root, 'foo')
    with pytest.raises(ImproperlyConfigured, message=message):
        migrations.get_known_versions()

    # correct path
    settings.NORTH_MIGRATIONS_ROOT = os.path.join(root, 'test_data/sql')
    result = migrations.get_known_versions()
    assert result == ['16.9', '16.11', '16.12', '17.01', '17.02', '17.3']


@pytest.mark.django_db
def test_get_applied_versions(mocker):
    mocker.patch(
        'django_north.management.migrations.get_known_versions',
        return_value=['1.0', '1.1', '1.2', '1.3', '1.10'])

    recorder = migrations.MigrationRecorder(connection)
    recorder.record_applied('1.10', 'fake-ddl.sql')
    result = migrations.get_applied_versions()
    assert result == ['1.0', '1.1', '1.2', '1.3', '1.10']


def test_get_migrations_to_apply(settings):
    root = os.path.dirname(__file__)
    settings.NORTH_MIGRATIONS_ROOT = os.path.join(root, 'test_data/sql')

    # version folder does not exist
    message = "No sql folder found for version foo."
    with pytest.raises(migrations.DBException, message=message):
        migrations.get_migrations_to_apply('foo')

    # no manual folder
    result = migrations.get_migrations_to_apply('17.02')
    migs = ['17.02-0-version-dml.sql',
            '17.02-feature_a-ddl.sql',
            '17.02-feature_b_manual-dml.sql',
            '17.02-feature_c_fakemanual-ddl.sql']
    assert result == {
        mig: os.path.join(
            settings.NORTH_MIGRATIONS_ROOT, '17.02', mig) for mig in migs
    }

    # with manual folder
    result = migrations.get_migrations_to_apply('17.01')
    migs = [
        '17.01-0-version-dml.sql',
        '17.01-feature_a-010-ddl.sql',
        '17.01-feature_a-020-ddl.sql',
        '17.01-feature_a-030-dml.sql',
        '17.01-feature_a-050-ddl.sql',
        '17.01-feature_b-ddl.sql',
    ]
    migration_dict = {
        mig: os.path.join(
            settings.NORTH_MIGRATIONS_ROOT, '17.01', mig) for mig in migs
    }
    migs = ['17.01-feature_a-040-dml.sql']
    migration_dict.update({
        mig: os.path.join(settings.NORTH_MIGRATIONS_ROOT, '17.01/manual', mig)
        for mig in migs
    })
    assert result == migration_dict


def test_build_migration_plan(settings, mocker):
    root = os.path.dirname(__file__)
    settings.NORTH_MIGRATIONS_ROOT = os.path.join(root, 'test_data/sql')
    settings.NORTH_TARGET_VERSION = '17.02'

    mock_get_applied_versions = mocker.patch(
        'django_north.management.migrations.get_applied_versions')
    mock_get_current_version = mocker.patch(
        'django_north.management.migrations.get_current_version')
    mock_get_applied_migrations = mocker.patch(
        'django_north.management.migrations.get_applied_migrations')
    mocker.patch(
        'django_north.management.migrations.get_known_versions',
        return_value=['16.11', '16.12', '17.01', '17.02'])

    plan1612 = {
        'version': '16.12',
        'plan': [],
    }
    migs = ['16.12-0-version-dml.sql']
    plan1612['plan'] += [
        (mig, True, os.path.join(settings.NORTH_MIGRATIONS_ROOT, '16.12', mig),
         False)
        for mig in migs
    ]
    plan1701 = {
        'version': '17.01',
        'plan': [],
    }
    migs = [
        '17.01-0-version-dml.sql',
        '17.01-feature_a-010-ddl.sql',
        '17.01-feature_a-020-ddl.sql',
        '17.01-feature_a-030-dml.sql',
    ]
    plan1701['plan'] += [
        (mig, False, os.path.join(
            settings.NORTH_MIGRATIONS_ROOT, '17.01', mig), False)
        for mig in migs
    ]
    migs = ['17.01-feature_a-040-dml.sql']
    plan1701['plan'] += [
        (mig, False, os.path.join(
            settings.NORTH_MIGRATIONS_ROOT, '17.01/manual', mig), True)
        for mig in migs
    ]
    migs = [
        '17.01-feature_a-050-ddl.sql',
        '17.01-feature_b-ddl.sql',
    ]
    plan1701['plan'] += [
        (mig, False, os.path.join(
            settings.NORTH_MIGRATIONS_ROOT, '17.01', mig), False)
        for mig in migs
    ]
    plan1702 = {
        'version': '17.02',
        'plan': [],
    }
    migs = [
        '17.02-0-version-dml.sql',
        '17.02-feature_a-ddl.sql',
    ]
    plan1702['plan'] += [
        (mig, False, os.path.join(
            settings.NORTH_MIGRATIONS_ROOT, '17.02', mig), False)
        for mig in migs
    ]
    migs = [
        '17.02-feature_b_manual-dml.sql',
    ]
    plan1702['plan'] += [
        (mig, False, os.path.join(
            settings.NORTH_MIGRATIONS_ROOT, '17.02', mig), True)
        for mig in migs
    ]
    migs = [
        '17.02-feature_c_fakemanual-ddl.sql',
    ]
    plan1702['plan'] += [
        (mig, False, os.path.join(
            settings.NORTH_MIGRATIONS_ROOT, '17.02', mig), False)
        for mig in migs
    ]

    # applied versions are empty
    mock_get_applied_versions.return_value = []
    # applied migrations too
    mock_get_applied_migrations.return_value = []

    # current version is None
    mock_get_current_version.return_value = None
    result = migrations.build_migration_plan()
    assert result is None

    # current version is not None
    mock_get_current_version.return_value = '16.12'
    result = migrations.build_migration_plan()
    assert result['current_version'] == '16.12'
    assert result['init_version'] == '16.12'
    assert len(result['plans']) == 2
    assert result['plans'][0] == plan1701
    assert result['plans'][1] == plan1702

    # current version is out of scope
    mock_get_current_version.return_value = 'foo'
    message = "The current version of the database is unknown: foo."
    with pytest.raises(migrations.DBException, message=message):
        migrations.build_migration_plan()

    # current version is the last one
    mock_get_current_version.return_value = '17.02'
    result = migrations.build_migration_plan()
    assert result['current_version'] == '17.02'
    assert result['init_version'] == '17.02'
    assert len(result['plans']) == 0

    mock_get_current_version.return_value = '16.12'

    # target version is out of scope
    settings.NORTH_TARGET_VERSION = 'foo'
    message = (
        "settings.NORTH_TARGET_VERSION is improperly configured: "
        "version foo not found.")
    with pytest.raises(ImproperlyConfigured, message=message):
        migrations.build_migration_plan()

    settings.NORTH_TARGET_VERSION = '17.02'

    # applied versions are not empty
    mock_get_applied_versions.return_value = ['16.12']
    # applied migrations
    mock_get_applied_migrations.side_effect = [
        ['16.12-0-version-dml.sql'],
        [],
        [],
    ]
    result = migrations.build_migration_plan()
    assert result['current_version'] == '16.12'
    assert result['init_version'] == '16.11'
    assert len(result['plans']) == 3
    assert result['plans'][0] == plan1612
    assert result['plans'][1] == plan1701
    assert result['plans'][2] == plan1702

    # current version is the last one
    mock_get_current_version.return_value = '17.02'
    # applied versions are not empty
    mock_get_applied_versions.return_value = ['17.02']
    # applied migrations
    mock_get_applied_migrations.side_effect = [
        [],
    ]
    result = migrations.build_migration_plan()
    assert result['current_version'] == '17.02'
    assert result['init_version'] == '17.01'
    assert len(result['plans']) == 1
    assert result['plans'][0] == plan1702

    # applied versions are not empty
    mock_get_applied_versions.return_value = ['17.01', '17.02']
    # applied migrations
    mock_get_applied_migrations.side_effect = [
        [],
        [],
    ]
    result = migrations.build_migration_plan()
    assert result['current_version'] == '17.02'
    assert result['init_version'] == '16.12'
    assert len(result['plans']) == 2
    assert result['plans'][0] == plan1701
    assert result['plans'][1] == plan1702

    # target version is not the last one
    settings.NORTH_TARGET_VERSION = '17.01'
    # current version is not the last one
    mock_get_current_version.return_value = '16.12'
    # applied versions are not empty
    mock_get_applied_versions.return_value = ['16.12', '17.01']
    # applied migrations
    mock_get_applied_migrations.side_effect = [
        ['16.12-0-version-dml.sql'],
        [],
    ]
    result = migrations.build_migration_plan()
    assert result['current_version'] == '16.12'
    assert result['init_version'] == '16.11'
    assert len(result['plans']) == 2
    assert result['plans'][0] == plan1612
    assert result['plans'][1] == plan1701

    # edge case: current version > target version
    mock_get_current_version.return_value = '17.02'
    # applied versions are not empty
    mock_get_applied_versions.return_value = ['16.12', '17.01', '17.02']
    # applied migrations
    mock_get_applied_migrations.side_effect = [
        ['16.12-0-version-dml.sql'],
        [],
        [],
    ]
    result = migrations.build_migration_plan()
    assert result['current_version'] == '17.02'
    assert result['init_version'] == '16.11'
    assert len(result['plans']) == 2
    assert result['plans'][0] == plan1612
    assert result['plans'][1] == plan1701


def test_get_version_for_init(settings, mocker):
    root = os.path.dirname(__file__)
    settings.NORTH_MIGRATIONS_ROOT = os.path.join(root, 'test_data/sql')
    mock_versions = mocker.patch(
        'django_north.management.migrations.get_known_versions')

    mock_versions.return_value = ['16.11', '16.12', '17.01', '17.02']

    # target version is out of scope
    settings.NORTH_TARGET_VERSION = 'foo'
    message = (
        "settings.NORTH_TARGET_VERSION is improperly configured: "
        "version foo not found.")
    with pytest.raises(ImproperlyConfigured, message=message):
        migrations.get_version_for_init()

    # schema for the version exists
    settings.NORTH_TARGET_VERSION = '17.02'
    assert migrations.get_version_for_init() == '17.02'

    # schema for the version does not exist, take the first ancestor
    settings.NORTH_TARGET_VERSION = '17.01'
    assert migrations.get_version_for_init() == '16.12'

    # no schema for the version, and no ancestors
    settings.NORTH_TARGET_VERSION = '16.11'
    message = "Can not find a schema to init the DB."
    with pytest.raises(migrations.DBException, message=message):
        migrations.get_version_for_init()

    # no ancestors, but the schema exists
    mock_versions.return_value = ['16.12', '17.01', '17.02']
    settings.NORTH_TARGET_VERSION = '17.01'
    assert migrations.get_version_for_init() == '16.12'

    # wrong template
    settings.NORTH_SCHEMA_TPL = 'foo.sql'
    with pytest.raises(migrations.DBException, message=message):
        migrations.get_version_for_init()
    settings.NORTH_SCHEMA_TPL = 'foo{}.sql'
    with pytest.raises(migrations.DBException, message=message):
        migrations.get_version_for_init()


def test_get_version_for_init_force_settings(settings, mocker):
    root = os.path.dirname(__file__)
    settings.NORTH_MIGRATIONS_ROOT = os.path.join(root, 'test_data/sql')
    mock_versions = mocker.patch(
        'django_north.management.migrations.get_known_versions')

    mock_versions.return_value = ['16.12', '17.1', '17.2', '17.3']

    # target version < schema
    settings.NORTH_TARGET_VERSION = '17.2'
    settings.NORTH_SCHEMA_VERSION = '17.3'
    message = (
        "settings.NORTH_TARGET_VERSION is improperly configured: "
        "settings.NORTH_SCHEMA_VERSION is more recent.")
    with pytest.raises(ImproperlyConfigured, message=message):
        migrations.get_version_for_init()

    # schema does not exist
    settings.NORTH_TARGET_VERSION = '17.3'
    settings.NORTH_SCHEMA_VERSION = '17.2'
    message = "Can not find a schema to init the DB."
    with pytest.raises(migrations.DBException, message=message):
        migrations.get_version_for_init()

    # ok, schema exists
    settings.NORTH_TARGET_VERSION = '17.3'
    settings.NORTH_SCHEMA_VERSION = '17.1'
    assert migrations.get_version_for_init() == '17.1'

    settings.NORTH_TARGET_VERSION = '17.3'
    settings.NORTH_SCHEMA_VERSION = '16.12'
    assert migrations.get_version_for_init() == '16.12'

    settings.NORTH_TARGET_VERSION = '17.3'
    settings.NORTH_SCHEMA_VERSION = '17.3'
    assert migrations.get_version_for_init() == '17.3'


def test_get_fixtures_for_init(settings, mocker):
    root = os.path.dirname(__file__)
    settings.NORTH_MIGRATIONS_ROOT = os.path.join(root, 'test_data/sql')
    mock_versions = mocker.patch(
        'django_north.management.migrations.get_known_versions')

    mock_versions.return_value = ['16.11', '16.12', '17.01', '17.02']

    # target version is out of scope
    message = (
        "settings.NORTH_TARGET_VERSION is improperly configured: "
        "version foo not found.")
    with pytest.raises(ImproperlyConfigured, message=message):
        migrations.get_fixtures_for_init('foo')

    # fixtures for the version exists
    assert migrations.get_fixtures_for_init('16.12') == '16.12'

    # fixtures for the version does not exist, take the first ancestor
    assert migrations.get_fixtures_for_init('17.01') == '16.12'

    # no fixtures for the version, and no ancestors
    message = "Can not find fixtures to init the DB."
    with pytest.raises(migrations.DBException, message=message):
        migrations.get_fixtures_for_init('16.11')

    # no ancestors, but fixtures exists
    mock_versions.return_value = ['16.12', '17.01', '17.02']
    assert migrations.get_fixtures_for_init('17.01') == '16.12'

    # wrong template
    settings.NORTH_FIXTURES_TPL = 'foo.sql'
    with pytest.raises(migrations.DBException, message=message):
        migrations.get_fixtures_for_init('16.12')
    settings.NORTH_FIXTURES_TPL = 'foo{}.sql'
    with pytest.raises(migrations.DBException, message=message):
        migrations.get_fixtures_for_init('16.12')
