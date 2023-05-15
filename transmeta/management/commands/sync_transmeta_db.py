"""
 Detect new translatable fields in all models and sync database structure.

 You will need to execute this command in two cases:

   1. When you add new languages to settings.LANGUAGES.
   2. When you new translatable fields to your models.

"""
# import re

from django.apps import apps
from django.conf import settings
from django.core.exceptions import FieldDoesNotExist
from django.core.management.base import BaseCommand
from django.core.management.color import no_style
from django.db import connection, transaction

from transmeta import (mandatory_language, get_real_fieldname,
                       get_languages, get_all_translatable_fields)

VALUE_DEFAULT = 'WITHOUT VALUE'


def ask_for_confirmation(sql_sentences, model_full_name, assume_yes):
    print('\nSQL to synchronize "%s" schema:' % model_full_name)
    for sentence in sql_sentences:
        print('   %s' % sentence)
    prompt = '\nAre you sure that you want to execute the previous SQL: (y/n) [n]: '
    if assume_yes:
        prompt += 'YES'
        print(prompt)
        return True
    while True:
        answer = input(prompt).strip().lower()
        if answer in ('y', 'yes'):
            return True
        if answer in ('', 'n', 'no'):
            return False
        print('Please answer yes or no')


def print_db_change_langs(db_change_langs, field_name, model_name):
    print(
        '\nChanged languages for "%s.%s": %s' %
        (model_name, field_name, ", ".join(db_change_langs))
    )


class Command(BaseCommand):
    help = "Detect new translatable fields or new available languages and sync database structure"

    def add_arguments(self, parser):
        parser.add_argument(
            '-y', '--yes',
            action='store_true', dest='assume_yes',
            help="Assume YES on all queries",
        )
        parser.add_argument(
            '-d', '--default', dest='default_language',
            help="Language code of your default language",
        )

    def handle(self, *args, **options):
        """ command execution """
        assume_yes = options.get('assume_yes', False)
        default_language = options.get('default_language', None)

        # set manual transaction management
        print('Warning: If you cancel (Ctrl-C) all changes will be rolled back')
        with transaction.atomic():
            self.cursor = connection.cursor()
            self.introspection = connection.introspection

            self.default_lang = default_language or mandatory_language()

            all_models = apps.get_models(include_swapped=True)
            found_db_change_fields = False
            languages = [i[0] for i in get_languages()]
            for model in all_models:
                if hasattr(model._meta, 'translatable_fields'):
                    model_full_name = model._meta.label_lower
                    translatable_fields = get_all_translatable_fields(model, column_in_current_table=True)
                    db_table = model._meta.db_table
                    for field_name in translatable_fields:
                        db_table_fields = self.get_table_fields(db_table)  # force re-read fields in each iteration
                        db_change_langs = self.get_db_change_languages(field_name, db_table_fields, languages)
                        if db_change_langs:
                            sql_sentences = self.get_sync_sql(field_name, db_change_langs, model, db_table_fields)
                            if sql_sentences:
                                found_db_change_fields = True
                                print_db_change_langs(db_change_langs, field_name, model_full_name)
                                execute_sql = ask_for_confirmation(sql_sentences, model_full_name, assume_yes)
                                if execute_sql:
                                    print('Executing SQL...')
                                    for sentence in sql_sentences:
                                        self.cursor.execute(sentence)
                                    print('Done')
                                else:
                                    print('SQL not executed')

        if not found_db_change_fields:
            print('\nNo new translatable fields detected')
        if default_language:
            variable = 'TRANSMETA_DEFAULT_LANGUAGE'
            has_transmeta_default_language = getattr(settings, variable, False)
            if not has_transmeta_default_language:
                variable = 'LANGUAGE_CODE'
            if getattr(settings, variable) != default_language:
                print(('\n\nYou should change in your settings '
                       'the %s variable to "%s"' % (variable, default_language)))

    def get_table_fields(self, db_table):
        """ get table fields from schema """
        db_table_desc = self.introspection.get_table_description(self.cursor, db_table)
        return [t[0] for t in db_table_desc]

    def get_field_required_in_db(self, db_table, field_name):
        table_fields = self.introspection.get_table_description(self.cursor, db_table)
        for f in table_fields:
            if f[0] == field_name:
                return not f.null_ok
        return False

    def get_db_change_languages(self, field_name, db_table_fields, languages):
        """get all languages we have to process for field"""
        return languages
        return [
            lang for lang in languages if get_real_fieldname(field_name, lang) not in db_table_fields
        ]
        # pattern = re.compile(r'^%s_(?P<lang>\w{2})$' % field_name)
        # for db_table_field in db_table_fields:
        #     m = pattern.match(db_table_field)
        #     if not m:
        #         continue
        #     lang = m.group('lang')
        #     if not lang in res:
        #         res.append(lang)

    def was_translatable_before(self, field_name, db_table_fields):
        """ check if field_name was translatable before syncing schema """
        if field_name in db_table_fields:
            # this implies field was never translatable before, data is in this field
            return False
        return True

    def get_default_field(self, field_name, model):
        for lang_code, lang_name in get_languages():
            field_name_i18n = get_real_fieldname(field_name, lang_code)
            f = model._meta.get_field(field_name_i18n)
            if not f.null:
                return f
        try:
            return model._meta.get_field(field_name)
        except FieldDoesNotExist:
            return None

    def get_value_default(self):
        return getattr(settings, 'TRANSMETA_VALUE_DEFAULT', VALUE_DEFAULT)

    def get_type_of_db_field(self, field_name, model):
        field = self.get_default_field(field_name, model)
        if not field:
            field = model._meta.get_field(get_real_fieldname(field_name))
        try:
            col_type = field.db_type(connection)
        except TypeError:  # old django
            col_type = field.db_type()
        return col_type

    def get_sync_sql(self, field_name, db_change_langs, model, db_table_fields):
        """ returns SQL needed for sync schema for a new translatable field """
        qn = connection.ops.quote_name
        style = no_style()
        sql_output = []
        db_table = model._meta.db_table
        was_translatable_before = self.was_translatable_before(field_name, db_table_fields)
        default_field = self.get_default_field(field_name, model)
        default_field_required = default_field and self.get_field_required_in_db(
            db_table,
            default_field.name,
        )
        for lang in db_change_langs:
            new_field = get_real_fieldname(field_name, lang)
            try:
                f = model._meta.get_field(new_field)
                col_type = self.get_type_of_db_field(field_name, model)
                field_column = f.column
            except FieldDoesNotExist:  # columns in db, removed the settings.LANGUGES
                field_column = new_field
                col_type = self.get_type_of_db_field(field_name, model)
            field_sql = [style.SQL_FIELD(qn(field_column)), style.SQL_COLTYPE(col_type)]

            alter_colum_set = 'ALTER COLUMN %s SET' % qn(field_column)
            if default_field:
                alter_colum_drop = 'ALTER COLUMN %s DROP' % qn(field_column)
            not_null = style.SQL_KEYWORD('NOT NULL')

            if connection.vendor == 'mysql':
                alter_colum_set = 'MODIFY %s %s' % (qn(field_column), col_type)
                not_null = style.SQL_KEYWORD('NULL')
                if default_field:
                    alter_colum_drop = 'MODIFY %s %s' % (qn(field_column), col_type)

            # column creation
            if new_field not in db_table_fields:
                sql_output.append(
                    "ALTER TABLE %s ADD COLUMN %s" % (qn(db_table), ' '.join(field_sql)))

            if lang == self.default_lang and not was_translatable_before:
                # data copy from old field (only for default language)
                sql_output.append(
                    "UPDATE %s SET %s = %s" % (qn(db_table), qn(field_column), qn(field_name)))
                if not f.null:
                    # changing to NOT NULL after having data copied
                    sql_output.append(
                        "ALTER TABLE %s %s %s" % (qn(db_table), alter_colum_set, style.SQL_KEYWORD('NOT NULL')))
            elif default_field and not default_field.null:
                if lang == self.default_lang:
                    f_required = self.get_field_required_in_db(
                        db_table,
                        field_column,
                    )
                    if default_field.name == new_field and default_field_required:
                        continue
                    if not f_required:
                        # data copy from old field (only for default language)
                        sql_output.append(
                            "UPDATE %(db_table)s SET %(f_column)s = '%(value_default)s' "
                            "WHERE %(f_column)s is %(null)s or %(f_column)s = '' " % {
                                'db_table': qn(db_table),
                                'f_column': qn(field_column),
                                'value_default': self.get_value_default(),
                                'null': style.SQL_KEYWORD('NULL'),
                            }
                        )
                        # changing to NOT NULL after having data copied
                        sql_output.append(
                            "ALTER TABLE %s %s %s" % (qn(db_table), alter_colum_set, style.SQL_KEYWORD('NOT NULL')))
                else:
                    f_required = self.get_field_required_in_db(
                        db_table,
                        field_column,
                    )
                    if f_required:
                        sql_output.append(
                            "ALTER TABLE %s %s %s" %
                            (qn(db_table), alter_colum_drop, not_null)
                        )

        if not was_translatable_before:
            # we drop field only if field was no translatable before
            sql_output.append("ALTER TABLE %s DROP COLUMN %s" % (qn(db_table), qn(field_name)))
        return sql_output
