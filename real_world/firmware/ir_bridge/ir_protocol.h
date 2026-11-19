// The IR receivers' RC protocol (v1.20): message encoding (no Arduino dependencies; host-testable with g++).
#pragma once
#include <stdint.h>

namespace irp {

// Pulse timings in microseconds (38 kHz carrier, one cycle = 26.3 us).
const uint16_t MARK_US = 158;         // 6 cycles of carrier
const uint16_t LOW_US = 263;          // 10 cycles of pause: bit 0
const uint16_t HIGH_US = 553;         // 21 cycles of pause: bit 1
const uint16_t START_STOP_US = 1026;  // 39 cycles of pause: start / stop
const uint8_t RAW_LEN = 35;           // start mark + space, 16 x (mark + space), stop mark
const uint16_t MESSAGE_GAP_MS = 16;   // gap between repeats of a message
const uint8_t CARRIER_KHZ = 38;

const int8_t BRAKE = 8;  // speed value meaning "brake, then float"

// 4-bit PWM code: 0 = float, 1..7 forward, -1..-7 backward (0xF..0x9), BRAKE = 0x8.
inline uint8_t pwm_nibble(int8_t step) {
  if (step == BRAKE) return 0x8;
  if (step > 7) step = 7;
  if (step < -7) step = -7;
  return step >= 0 ? (uint8_t)step : (uint8_t)(16 + step);
}

// Three nibbles plus their check nibble (LRC = 0xF xor n1 xor n2 xor n3).
inline uint16_t message(uint8_t n1, uint8_t n2, uint8_t n3) {
  uint8_t lrc = 0xF ^ n1 ^ n2 ^ n3;
  return (uint16_t)(((n1 & 0xF) << 12) | ((n2 & 0xF) << 8) | ((n3 & 0xF) << 4) | (lrc & 0xF));
}

// Single output mode, PWM: the receiver keeps the speed until the next command (no timeout).
// channel 0..3 (switch 1..4), output 0 = red (A), 1 = blue (B).
inline uint16_t single_pwm(uint8_t toggle, uint8_t channel, uint8_t output, int8_t step) {
  return message((uint8_t)(((toggle & 1) << 3) | (channel & 3)), (uint8_t)(0x4 | (output & 1)), pwm_nibble(step));
}

// Combo PWM mode: both outputs in one message; the receiver stops them after ~1.2 s without a new message.
inline uint16_t combo_pwm(uint8_t channel, int8_t step_a, int8_t step_b) {
  return message((uint8_t)(0x4 | (channel & 3)), pwm_nibble(step_b), pwm_nibble(step_a));
}

// Mark / space durations of one message (most significant bit first) for IrSender.sendRaw().
inline void raw_timings(uint16_t msg, uint16_t buf[RAW_LEN]) {
  uint8_t i = 0;
  buf[i++] = MARK_US;
  buf[i++] = START_STOP_US;
  for (int8_t bit = 15; bit >= 0; --bit) {
    buf[i++] = MARK_US;
    buf[i++] = ((msg >> bit) & 1) ? HIGH_US : LOW_US;
  }
  buf[i++] = MARK_US;  // stop bit
}

}  // namespace irp
