// origin: https://googlechromelabs.github.io/web-audio-samples/audio-worklet/migration/worklet-recorder/

// Copyright (c) 2022 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

class RecordingProcessor extends AudioWorkletProcessor {
  constructor(options) {
    super();

    this.sampleRate = 16000;
    this.maxRecordingFrames = 0;
    this.numberOfChannels = 1;

    if (options && options.processorOptions) {
      const {
        numberOfChannels,
        sampleRate,
        maxFrameCount,
      } = options.processorOptions;

      this.sampleRate = sampleRate;
      this.maxRecordingFrames = maxFrameCount;
      this.numberOfChannels = numberOfChannels;
    }

    // Initialize _recordingBuffer as a Uint8Array
    this._recordingBuffer = new Uint8Array(this.maxRecordingFrames * 2);

    this.recordedFrames = 0;
    this.isRecording = false;
    this.lastSentFrame = 0;

    // We will use a timer to gate our messages; this one will publish at 30hz
    this.framesSinceLastPublish = 0;
    this.publishInterval = this.sampleRate / 30;

    // We will keep a live sum for rendering the visualizer.
    this.sampleSum = 0;

    this.port.onmessage = (event) => {
      if (event.data.message === 'UPDATE_RECORDING_STATE') {
        this.isRecording = event.data.setRecording;

        if (this.isRecording === false) {
          this.port.postMessage({
            message: 'SHARE_RECORDING_BUFFER',
            buffer: this._recordingBuffer,
            recordingLength: this.recordedFrames, // ADDED
          });
        } else {
          this.recordedFrames = 0; // RESET ON START to handle multiple sessions ADDED
        }
      }
    };
  }

  process(inputs, outputs, params) {
    // Assuming we are only interested in the first channel 0  // TODO: convert to mono properly
    let inputBuffer = inputs[0][0];
    for (let sample = 0; sample < inputBuffer.length; ++sample) {
      let currentSample = inputBuffer[sample];

      if (this.isRecording) {
        // Copy data to recording buffer
        let signed16bits = Math.max(-32768, 
                                    Math.min(32767, currentSample * 32768.0));
        let index = (sample + this.recordedFrames) * 2;
        this._recordingBuffer[index] = signed16bits & 255; // low byte, little endian
        this._recordingBuffer[index + 1] = (signed16bits >> 8) & 255; // high
      }
  
      // Sum values for visualizer
      this.sampleSum += Math.abs(currentSample);  // CHANGED to absolute values [0, 1]
    }
      
    const shouldPublish = this.framesSinceLastPublish >= this.publishInterval;

    // Validate that recording hasn't reached its limit.
    if (this.isRecording) {
      if (this.recordedFrames + 128 < this.maxRecordingFrames) {
        this.recordedFrames += 128;

        // Post a recording recording length update on the clock's schedule
        if (shouldPublish) {
          let bufferSlice = this._recordingBuffer.slice(
            this.lastSentFrame * 2, this.recordedFrames * 2);

          this.port.postMessage({
            message: 'UPDATE_RECORDING',
            recordingLength: this.recordedFrames,
            bufferSlice: bufferSlice,
          });

          this.lastSentFrame = this.recordedFrames;
        }
      } else {
        // Let the rest of the app know the limit was reached.
        this.isRecording = false;
        this.port.postMessage({
          message: 'MAX_RECORDING_LENGTH_REACHED',
          buffer: this._recordingBuffer,
        });

        this.recordedFrames += 128;
        this.port.postMessage({
          message: 'UPDATE_RECORDING_LENGTH',
          recordingLength: this.recordedFrames,
        });

        return false;
      }
    }

    // Handle message clock.
    // If we should publish, post message and reset clock.
    if (shouldPublish) {
      this.port.postMessage({
        message: 'UPDATE_VISUALIZERS',
        gain: this.sampleSum / this.framesSinceLastPublish,
      });

      this.framesSinceLastPublish = 0;
      this.sampleSum = 0;
    } else {
      this.framesSinceLastPublish += 128;
    }

    return true;
  }
}

registerProcessor('recording-processor', RecordingProcessor);
