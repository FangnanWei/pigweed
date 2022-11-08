#!/usr/bin/env python3
# Copyright 2022 The Pigweed Authors
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may not
# use this file except in compliance with the License. You may obtain a copy of
# the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations under
# the License.
"""Cross-language pw_transfer tests that take several seconds each.

Usage:

   bazel run pw_transfer/integration_test:cross_language_medium_test

Command-line arguments must be provided after a double-dash:

   bazel run pw_transfer/integration_test:cross_language_medium_test -- \
       --server-port 3304

Which tests to run can be specified as command-line arguments:

  bazel run pw_transfer/integration_test:cross_language_medium_test -- \
      MediumTransferIntegrationTest.test_medium_client_write_1_java

"""

import itertools
from parameterized import parameterized
import random

from google.protobuf import text_format

from pigweed.pw_transfer.integration_test import config_pb2
import test_fixture
from test_fixture import TransferIntegrationTestHarness, TransferConfig


class MediumTransferIntegrationTest(test_fixture.TransferIntegrationTest):
    # Each set of transfer tests uses a different client/server port pair to
    # allow tests to be run in parallel.
    HARNESS_CONFIG = TransferIntegrationTestHarness.Config(server_port=3304,
                                                           client_port=3305)

    @parameterized.expand(
        itertools.product(("cpp", "java", "python"),
                          (config_pb2.TransferAction.ProtocolVersion.V1,
                           config_pb2.TransferAction.ProtocolVersion.V2)))
    def test_medium_client_write(self, client_type, protocol_version):
        payload = random.Random(67336391945).randbytes(512)
        config = self.default_config()
        resource_id = 5
        self.do_single_write(client_type, config, resource_id, payload,
                             protocol_version)

    @parameterized.expand(
        itertools.product(("cpp", "java", "python"),
                          (config_pb2.TransferAction.ProtocolVersion.V1,
                           config_pb2.TransferAction.ProtocolVersion.V2)))
    def test_large_hdlc_escape_client_write(self, client_type,
                                            protocol_version):
        payload = b"~" * 98731
        config = self.default_config()
        resource_id = 5
        self.do_single_write(client_type, config, resource_id, payload,
                             protocol_version)

    @parameterized.expand(
        itertools.product(("cpp", "java", "python"),
                          (config_pb2.TransferAction.ProtocolVersion.V1,
                           config_pb2.TransferAction.ProtocolVersion.V2)))
    def test_pattern_drop_client_write(self, client_type, protocol_version):
        """Drops packets with an alternating pattern."""
        payload = random.Random(67336391945).randbytes(1234)
        config = TransferConfig(
            self.default_server_config(), self.default_client_config(),
            text_format.Parse(
                """
                client_filter_stack: [
                    { hdlc_packetizer: {} },
                    { keep_drop_queue: {keep_drop_queue: [5, 1]} }
                ]

                server_filter_stack: [
                    { hdlc_packetizer: {} },
                    { keep_drop_queue: {keep_drop_queue: [3, 1]} }
            ]""", config_pb2.ProxyConfig()))
        resource_id = 1337

        # This test deliberately causes flakes during the opening handshake of
        # a transfer, so allow the resource_id of this transfer to be reused
        # multiple times.
        max_attempts = self.default_client_config().max_retries + 1
        self.do_single_write(client_type,
                             config,
                             resource_id,
                             payload,
                             protocol_version,
                             max_attempts=max_attempts)

    @parameterized.expand(
        itertools.product(("cpp", "java", "python"),
                          (config_pb2.TransferAction.ProtocolVersion.V1,
                           config_pb2.TransferAction.ProtocolVersion.V2)))
    def test_parameter_drop_client_write(self, client_type, protocol_version):
        """Drops the first few transfer initialization packets."""
        payload = random.Random(67336391945).randbytes(1234)
        config = TransferConfig(
            self.default_server_config(), self.default_client_config(),
            text_format.Parse(
                """
                client_filter_stack: [
                    { hdlc_packetizer: {} },
                    { keep_drop_queue: {keep_drop_queue: [2, 1, -1]} }
                ]

                server_filter_stack: [
                    { hdlc_packetizer: {} },
                    { keep_drop_queue: {keep_drop_queue: [1, 2, -1]} }
            ]""", config_pb2.ProxyConfig()))
        resource_id = 1337
        self.do_single_write(client_type, config, resource_id, payload,
                             protocol_version)

    @parameterized.expand(
        itertools.product(("cpp", "java", "python"),
                          (config_pb2.TransferAction.ProtocolVersion.V1,
                           config_pb2.TransferAction.ProtocolVersion.V2)))
    def test_medium_client_read(self, client_type, protocol_version):
        payload = random.Random(67336391945).randbytes(512)
        config = self.default_config()
        resource_id = 5
        self.do_single_read(client_type, config, resource_id, payload,
                            protocol_version)

    @parameterized.expand(
        itertools.product(("cpp", "java", "python"),
                          (config_pb2.TransferAction.ProtocolVersion.V1,
                           config_pb2.TransferAction.ProtocolVersion.V2)))
    def test_large_hdlc_escape_client_read(self, client_type,
                                           protocol_version):
        payload = b"~" * 98731
        config = self.default_config()
        resource_id = 5
        self.do_single_read(client_type, config, resource_id, payload,
                            protocol_version)

    @parameterized.expand(
        itertools.product(("cpp", "java", "python"),
                          (config_pb2.TransferAction.ProtocolVersion.V1,
                           config_pb2.TransferAction.ProtocolVersion.V2)))
    def test_pattern_drop_client_read(self, client_type, protocol_version):
        """Drops packets with an alternating pattern."""
        payload = random.Random(67336391945).randbytes(1234)
        config = TransferConfig(
            self.default_server_config(), self.default_client_config(),
            text_format.Parse(
                """
                client_filter_stack: [
                    { hdlc_packetizer: {} },
                    { keep_drop_queue: {keep_drop_queue: [5, 1]} }
                ]

                server_filter_stack: [
                    { hdlc_packetizer: {} },
                    { keep_drop_queue: {keep_drop_queue: [3, 1]} }
            ]""", config_pb2.ProxyConfig()))
        resource_id = 1337

        # This test causes flakes during the opening handshake of a transfer, so
        # allow the resource_id of this transfer to be reused multiple times.
        max_attempts = self.default_client_config().max_retries + 1
        self.do_single_read(client_type,
                            config,
                            resource_id,
                            payload,
                            protocol_version,
                            max_attempts=max_attempts)

    @parameterized.expand(
        itertools.product(("cpp", "java", "python"),
                          (config_pb2.TransferAction.ProtocolVersion.V1,
                           config_pb2.TransferAction.ProtocolVersion.V2)))
    def test_parameter_drop_client_read(self, client_type, protocol_version):
        """Drops the first few transfer initialization packets."""
        # TODO(b/257308150): Python v2 breaks and the transfer fails on this
        # test.
        if (client_type == "python" and protocol_version
                == config_pb2.TransferAction.ProtocolVersion.V2):
            self.skipTest(
                "This test fails when using v2 protocol with a Python client")
        payload = random.Random(67336391945).randbytes(1234)
        config = TransferConfig(
            self.default_server_config(), self.default_client_config(),
            text_format.Parse(
                """
                client_filter_stack: [
                    { hdlc_packetizer: {} },
                    { keep_drop_queue: {keep_drop_queue: [2, 1, -1]} }
                ]

                server_filter_stack: [
                    { hdlc_packetizer: {} },
                    { keep_drop_queue: {keep_drop_queue: [1, 2, -1]} }
            ]""", config_pb2.ProxyConfig()))
        resource_id = 1337

        # This test deliberately causes flakes during the opening handshake of
        # a transfer, so allow the resource_id of this transfer to be reused
        # multiple times.
        max_attempts = self.default_client_config().max_retries + 1
        self.do_single_read(client_type,
                            config,
                            resource_id,
                            payload,
                            protocol_version,
                            max_attempts=max_attempts)


if __name__ == '__main__':
    test_fixture.run_tests_for(MediumTransferIntegrationTest)
