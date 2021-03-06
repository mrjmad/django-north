from django.core.management import call_command
from django.utils.six import StringIO
from django.utils.version import get_docs_version

import pytest


@pytest.mark.django_db
def test_sqlall(mocker, settings):
    stdout = mocker.patch('sys.stdout', new_callable=StringIO)
    mocker.patch(
        'django.db.backends.base.schema.BaseDatabaseSchemaEditor'
        '._create_index_name',
        return_value='INDEX_NAME')

    call_command('sqlall', 'north_app')

    assert stdout.getvalue() == (
        'BEGIN;\n'
        'CREATE TABLE "north_app_author" '
        '("id" serial NOT NULL PRIMARY KEY, "name" varchar(100) NOT NULL)\n'
        'CREATE TABLE "north_app_reader" '
        '("id" serial NOT NULL PRIMARY KEY, "name" varchar(100) NOT NULL)\n'
        'CREATE TABLE "north_app_book_readers" '
        '("id" serial NOT NULL PRIMARY KEY, '
        '"book_id" integer NOT NULL, '
        '"reader_id" integer NOT NULL)\n'
        'CREATE TABLE "north_app_book" '
        '("id" serial NOT NULL PRIMARY KEY, '
        '"author_id" integer NOT NULL, '
        '"title" varchar(100) NOT NULL, '
        '"pages" integer NOT NULL)\n'
        'ALTER TABLE "north_app_book_readers" '
        'ADD CONSTRAINT "INDEX_NAME" FOREIGN KEY ("book_id") '
        'REFERENCES "north_app_book" ("id") DEFERRABLE INITIALLY DEFERRED\n'
        'ALTER TABLE "north_app_book_readers" '
        'ADD CONSTRAINT "INDEX_NAME" FOREIGN KEY ("reader_id") '
        'REFERENCES "north_app_reader" ("id") DEFERRABLE INITIALLY DEFERRED\n'
        'ALTER TABLE "north_app_book_readers" '
        'ADD CONSTRAINT "INDEX_NAME" UNIQUE ("book_id", "reader_id")\n'
        'CREATE INDEX "INDEX_NAME" ON "north_app_book_readers" ("book_id")\n'
        'CREATE INDEX "INDEX_NAME" ON "north_app_book_readers" ("reader_id")\n'
        'ALTER TABLE "north_app_book" '
        'ADD CONSTRAINT "INDEX_NAME" '
        'FOREIGN KEY ("author_id") REFERENCES "north_app_author" ("id") '
        'DEFERRABLE INITIALLY DEFERRED\n'
        'CREATE INDEX "INDEX_NAME" ON "north_app_book" ("author_id")\n'
        + '\n' * (0 if get_docs_version() in ['1.10', '1.11'] else 1)
        + 'COMMIT;\n'
    )
