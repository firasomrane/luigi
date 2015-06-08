# -*- coding: utf-8 -*-
#
# Copyright 2015 Twitter Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

"""This is an integration test for the Bigquery-luigi binding.

This test requires credentials that can access GCS & access to a bucket below.
Follow the directions in the gcloud tools to set up local credentials.
"""

import json
import os

import luigi
from luigi.contrib import bigquery
from luigi.contrib import gcs

from contrib import _gcs_test

PROJECT_ID = _gcs_test.PROJECT_ID
DATASET_ID = os.environ.get('BQ_TEST_DATASET_ID', 'luigi_tests')


class TestLoadTask(bigquery.BigqueryLoadTask):
    _BIGQUERY_CLIENT = None

    source = luigi.Parameter()
    table = luigi.Parameter()

    @property
    def schema(self):
        return [
            {'mode': 'NULLABLE', 'name': 'field1', 'type': 'STRING'},
            {'mode': 'NULLABLE', 'name': 'field2', 'type': 'INTEGER'},
        ]

    def source_uris(self):
        return [self.source]

    def output(self):
        return bigquery.BigqueryTarget(PROJECT_ID, DATASET_ID, self.table,
                                       client=self._BIGQUERY_CLIENT)


class TestRunQueryTask(bigquery.BigqueryRunQueryTask):
    _BIGQUERY_CLIENT = None

    query = ''' SELECT 'hello' as field1, 2 as field2 '''
    table = luigi.Parameter()

    def output(self):
        return bigquery.BigqueryTarget(PROJECT_ID, DATASET_ID, self.table,
                                       client=self._BIGQUERY_CLIENT)


class BigqueryTest(_gcs_test._GCSBaseTestCase):
    def setUp(self):
        super(BigqueryTest, self).setUp()
        self.bq_client = bigquery.BigqueryClient(_gcs_test.CREDENTIALS)

        self.table_id = self.id().split('.')[-1]
        self.addCleanup(self.bq_client.delete_table, PROJECT_ID, DATASET_ID, self.table_id)

    def create_dataset(self, data=[]):
        self.bq_client.delete_table(PROJECT_ID, DATASET_ID, self.table_id)

        text = '\n'.join(map(json.dumps, data))
        gcs_file = _gcs_test.bucket_url(self.id())
        self.client.put_string(text, gcs_file)

        task = TestLoadTask(source=gcs_file, table=self.table_id)
        task._BIGQUERY_CLIENT = self.bq_client

        task.run()

    def test_load_and_copy(self):
        self.create_dataset([
            {'field1': 'hi', 'field2': 1},
            {'field1': 'bye', 'field2': 2},
        ])

        # Cram some stuff in here to make the tests run faster - loading data takes a while!
        self.assertTrue(self.bq_client.exists(PROJECT_ID, DATASET_ID, self.table_id))
        self.assertIn(DATASET_ID, list(self.bq_client.list_datasets(PROJECT_ID)))
        self.assertIn(self.table_id, list(self.bq_client.list_tables(PROJECT_ID, DATASET_ID)))

        self.bq_client.copy(
            source_project_id=PROJECT_ID,
            dest_project_id=PROJECT_ID,
            source_dataset_id=DATASET_ID,
            dest_dataset_id=DATASET_ID,
            source_table_id=self.table_id,
            dest_table_id=self.table_id + '_copy',
        )
        self.assertTrue(self.bq_client.exists(PROJECT_ID, DATASET_ID, self.table_id + '_copy'))
        self.bq_client.delete_table(PROJECT_ID, DATASET_ID, self.table_id + '_copy')
        self.assertFalse(self.bq_client.exists(PROJECT_ID, DATASET_ID, self.table_id + '_copy'))

    def test_run_query(self):
        task = TestRunQueryTask(table=self.table_id)
        task._BIGQUERY_CLIENT = self.bq_client
        task.run()

        self.assertTrue(self.bq_client.exists(PROJECT_ID, DATASET_ID, self.table_id))
