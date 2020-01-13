// Copyright 2020 The Pigweed Authors
//
// Licensed under the Apache License, Version 2.0 (the "License"); you may not
// use this file except in compliance with the License. You may obtain a copy of
// the License at
//
//     https://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
// WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
// License for the specific language governing permissions and limitations under
// the License.

#include "pw_bloat/bloat_this_binary.h"
#include "pw_protobuf/decoder.h"

namespace {
// clang-format off
constexpr uint8_t encoded_proto[] = {
  // type=int32, k=1, v=42
  0x08, 0x2a,
  // type=sint32, k=2, v=-13
  0x10, 0x19,
};
// clang-format on
}  // namespace

class TestDecodeHandler : public pw::protobuf::DecodeHandler {
 public:
  pw::Status ProcessField(pw::protobuf::Decoder* decoder,
                          uint32_t field_number) override {
    switch (field_number) {
      case 1:
        if (!decoder->ReadInt32(field_number, &test_int32).ok()) {
          test_int32 = 0;
        }
        break;
      case 2:
        if (!decoder->ReadSint32(field_number, &test_sint32).ok()) {
          test_sint32 = 0;
        }
        break;
      case 3:
        if (!decoder->ReadInt32(field_number, &test_int32).ok()) {
          test_int32 = 0;
        }
        break;
      case 4:
        if (!decoder->ReadInt32(field_number, &test_int32).ok()) {
          test_int32 = 0;
        }
        break;
      case 5:
        if (!decoder->ReadInt32(field_number, &test_int32).ok()) {
          test_int32 = 0;
        }
        break;
      case 6:
        if (!decoder->ReadSint32(field_number, &test_sint32).ok()) {
          test_sint32 = 0;
        }
        break;
      case 7:
        if (!decoder->ReadSint32(field_number, &test_sint32).ok()) {
          test_sint32 = 0;
        }
        break;
    }

    return pw::Status::OK;
  }

  int32_t test_int32 = 0;
  int32_t test_sint32 = 0;
};

int* volatile non_optimizable_pointer;

int main() {
  pw::bloat::BloatThisBinary();

  pw::protobuf::Decoder decoder;
  TestDecodeHandler handler;

  decoder.set_handler(&handler);
  decoder.Decode(pw::as_bytes(pw::span(encoded_proto)));

  *non_optimizable_pointer = handler.test_int32 + handler.test_sint32;

  return 0;
}
