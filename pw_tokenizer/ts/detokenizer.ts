// Copyright 2022 The Pigweed Authors
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

/**  Decodes and detokenizes strings from binary or Base64 input. */
import {Buffer} from 'buffer';
import {Frame} from '@pigweed/pw_hdlc';
import {TokenDatabase} from './token_database';
import {PrintfDecoder} from './printf_decoder';

const BASE64CHARS = '[A-Za-z0-9+/-_]';
const PATTERN = new RegExp(
  // Base64 tokenized strings start with the prefix character ($)
  '\\$' +
    // Tokenized strings contain 0 or more blocks of four Base64 chars.
    `(?:${BASE64CHARS}{4})*` +
    // The last block of 4 chars may have one or two padding chars (=).
    `(?:${BASE64CHARS}{3}=|${BASE64CHARS}{2}==)?`,
  'g'
);

interface TokenAndArgs {
  token: number;
  args: Uint8Array;
}

export class Detokenizer {
  private database: TokenDatabase;

  constructor(csvDatabase: string) {
    this.database = new TokenDatabase(csvDatabase);
  }

  /**
   * Detokenize frame data into actual string messages using the provided
   * token database.
   *
   * If the frame doesn't match any token from database, the frame will be
   * returned as string as-is.
   */
  detokenize(tokenizedFrame: Frame): string {
    const {token, args} = this.decodeTokenFrame(tokenizedFrame);
    // Parse arguments if this is printf-style text.
    const format = this.database.get(token);
    if (format) {
      return new PrintfDecoder().decode(String(format), args);
    }

    return new TextDecoder().decode(tokenizedFrame.data);
  }

  /**
   * Detokenize Base64-encoded frame data into actual string messages using the
   * provided token database.
   *
   * If the frame doesn't match any token from database, the frame will be
   * returned as string as-is.
   */
  detokenizeBase64(tokenizedFrame: Frame): string {
    const base64Frame = new TextDecoder().decode(tokenizedFrame.data);
    return base64Frame.replace(PATTERN, base64Substring => {
      const {token, args} = this.decodeBase64TokenFrame(base64Substring);
      const format = this.database.get(token);
      // Parse arguments if this is printf-style text.
      if (format) {
        return new PrintfDecoder().decode(String(format), args);
      }
      return base64Substring;
    });
  }

  private decodeTokenFrame(frame: Frame): TokenAndArgs {
    const token = new DataView(
      frame.data.buffer,
      frame.data.byteOffset,
      4
    ).getUint32(0, true);
    const args = new Uint8Array(frame.data.buffer.slice(4));

    return {token, args};
  }

  private decodeBase64TokenFrame(base64Data: string): TokenAndArgs {
    // Remove the prefix '$' and convert from Base64.
    const prefixRemoved = base64Data.slice(1);
    const noBase64 = Buffer.from(prefixRemoved, 'base64').toString('binary');
    // Convert back to bytes and return token and arguments.
    const bytes = noBase64.split('').map(ch => ch.charCodeAt(0));
    const uIntArray = new Uint8Array(bytes);
    const token = new DataView(
      uIntArray.buffer,
      uIntArray.byteOffset,
      4
    ).getUint32(0, true);
    const args = new Uint8Array(bytes.slice(4));

    return {token, args};
  }
}