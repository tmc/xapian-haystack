# Copyright (C) 2009 David Sauve
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.

import datetime
import os

from django.conf import settings
from django.test import TestCase

from haystack.query import QF
from haystack.backends.xapian_backend import SearchBackend, SearchQuery

from core.models import MockModel, AnotherMockModel


class XapianSearchQueryTestCase(TestCase):
    def setUp(self):
        super(XapianSearchQueryTestCase, self).setUp()

        # Stow.
        temp_path = os.path.join('tmp', 'test_xapian_query')
        self.old_xapian_path = getattr(settings, 'HAYSTACK_XAPIAN_PATH', temp_path)
        settings.HAYSTACK_XAPIAN_PATH = temp_path

        self.sq = SearchQuery(backend=SearchBackend())

    def tearDown(self):
        if os.path.exists(settings.HAYSTACK_XAPIAN_PATH):
            index_files = os.listdir(settings.HAYSTACK_XAPIAN_PATH)

            for index_file in index_files:
                os.remove(os.path.join(settings.HAYSTACK_XAPIAN_PATH, index_file))

            os.removedirs(settings.HAYSTACK_XAPIAN_PATH)

        settings.HAYSTACK_XAPIAN_PATH = self.old_xapian_path
        super(XapianSearchQueryTestCase, self).tearDown()

    def test_build_query_all(self):
        self.assertEqual(self.sq.build_query(), '*')

    def test_build_query_single_word(self):
        self.sq.add_filter(QF(content='hello'))
        self.assertEqual(self.sq.build_query(), 'hello')

    def test_build_query_multiple_words_and(self):
        self.sq.add_filter(QF(content='hello'))
        self.sq.add_filter(QF(content='world'))
        self.assertEqual(self.sq.build_query(), '(hello AND world)')

    def test_build_query_multiple_words_not(self):
        self.sq.add_filter(~QF(content='hello'))
        self.sq.add_filter(~QF(content='hello'))
        self.assertEqual(self.sq.build_query(), '(NOT (hello) AND NOT (hello))')

    def test_build_query_multiple_words_or(self):
        self.sq.add_filter(QF(content='hello'), use_or=True)
        self.sq.add_filter(QF(content='world'), use_or=True)
        self.assertEqual(self.sq.build_query(), '(hello OR world)')

    def test_build_query_multiple_words_mixed(self):
        self.sq.add_filter(QF(content='why'))
        self.sq.add_filter(QF(content='hello'), use_or=True)
        self.sq.add_filter(~QF(content='world'))
        self.assertEqual(self.sq.build_query(), '((why OR hello) AND NOT (world))')

    def test_build_query_phrase(self):
        self.sq.add_filter(QF(content='hello world'))
        self.assertEqual(self.sq.build_query(), '"hello world"')

    def test_build_query_multiple_filter_types(self):
        self.sq.add_filter(QF(content='why'))
        self.sq.add_filter(QF(pub_date__lte=datetime.datetime(2009, 2, 10, 1, 59)))
        self.sq.add_filter(QF(author__gt='david'))
        self.sq.add_filter(QF(created__lt=datetime.datetime(2009, 2, 12, 12, 13)))
        self.sq.add_filter(QF(title__gte='B'))
        self.sq.add_filter(QF(id__in=[1, 2, 3]))
        self.assertEqual(self.sq.build_query(), '(why AND pub_date:..20090210015900 AND NOT author:..david AND NOT created:20090212121300..* AND title:B..* AND (id:1 OR id:2 OR id:3))')

    def test_build_query_multiple_exclude_types(self):
        self.sq.add_filter(~QF(content='why'))
        self.sq.add_filter(~QF(pub_date__lte=datetime.datetime(2009, 2, 10, 1, 59)))
        self.sq.add_filter(~QF(author__gt='david'))
        self.sq.add_filter(~QF(created__lt=datetime.datetime(2009, 2, 12, 12, 13)))
        self.sq.add_filter(~QF(title__gte='B'))
        self.sq.add_filter(~QF(id__in=[1, 2, 3]))
        self.assertEqual(self.sq.build_query(), '(NOT (why) AND NOT (pub_date:..20090210015900) AND NOT (NOT author:..david) AND NOT (NOT created:20090212121300..*) AND NOT (title:B..*) AND NOT ((id:1 OR id:2 OR id:3)))')

    def test_build_query_wildcard_filter_types(self):
        self.sq.add_filter(QF(content='why'))
        self.sq.add_filter(QF(title__startswith='haystack'))
        self.assertEqual(self.sq.build_query(), '(why AND title:haystack*)')

    def test_clean(self):
        self.assertEqual(self.sq.clean('hello world'), 'hello world')
        self.assertEqual(self.sq.clean('hello AND world'), 'hello and world')
        self.assertEqual(self.sq.clean('hello AND OR NOT + - && || ! ( ) { } [ ] ^ " ~ * ? : \ world'), 'hello and or not \\+ \\- \\&& \\|| \\! \\( \\) \\{ \\} \\[ \\] \\^ \\" \\~ \\* \\? \\: \\\\ world')
        self.assertEqual(self.sq.clean('so please NOTe i am in a bAND and bORed'), 'so please NOTe i am in a bAND and bORed')

    def test_build_query_with_models(self):
        self.sq.add_filter(QF(content='hello'))
        self.sq.add_model(MockModel)
        self.assertEqual(self.sq.build_query(), u'(hello) AND (django_ct:core.mockmodel)')

        self.sq.add_model(AnotherMockModel)
        self.assertEqual(self.sq.build_query(), u'(hello) AND (django_ct:core.mockmodel OR django_ct:core.anothermockmodel)')

    def test_build_query_with_datetime(self):
        self.sq.add_filter(QF(pub_date=datetime.datetime(2009, 5, 9, 16, 20)))
        self.assertEqual(self.sq.build_query(), u'pub_date:20090509162000')

    def test_build_query_with_sequence_and_filter_not_in(self):
        self.sq.add_filter(QF(id__exact=[1, 2, 3]))
        self.assertEqual(self.sq.build_query(), u'id:[1, 2, 3]')