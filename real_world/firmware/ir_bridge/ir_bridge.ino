// USB-serial -> IR bridge for the robots' IR receivers, for Arduino Uno / Nano (and ESP32).
// Library: "IRremote" by Armin Joachimsmeyer (v4.x), from the Arduino Library Manager.
// IR output: pin 3 on Uno/Nano (fixed by the timer IRremote uses), pin 4 on ESP32.
//
// Wiring (real_world/README.md, "IR emitter"): one 940 nm IR LED reaches every receiver (each command carries its
// channel); a second LED is optional, for coverage only. Both flash together, so nothing changes in this code.
//
//   pin 3 ──[1 kΩ]──► base    NPN transistor (2N2222 / PN2222 / BC337)
//                             emitter ──► GND
//   5 V ──[47 Ω]──►|── IR LED 1 ──┐
//   5 V ──[47 Ω]──►|── IR LED 2 ──┴──► collector
//          (anode → cathode; the cathode is the short leg / flat side)
//
// Each LED has its own 47 Ω resistor (~70 mA in short 38 kHz bursts, within the LED's pulse rating). Without a
// transistor: one or two LEDs straight from pin 3 to GND through 220 Ω each (~15 mA, shorter range).
//
// One command per line, 115200 baud; the board answers "OK ..." or "ERR ...":
//   ?                         ping
//   P <ch> <A|B> <speed>      single output, latched          e.g.  P 1 A 5   P 1 B -7   P 1 A brake
//   C <ch> <speedA> <speedB>  both outputs (stops after ~1 s unless repeated)   e.g.  C 1 7 0
//   N <repeats>               send each message 1..10 times (default 3)
// ch = 1..4 (the receiver's orange channel switch), speed = -7..7 (0 = float) or "brake".

#if defined(ESP32)
#define IR_PIN 4
#else
#define IR_PIN 3
#endif

#include <IRremote.hpp>
#include "ir_protocol.h"

static uint8_t repeats = 3;
static uint8_t toggle = 0;
static char line[48];
static uint8_t line_len = 0;

static void send_message(uint16_t msg) {
  uint16_t buf[irp::RAW_LEN];
  irp::raw_timings(msg, buf);
  for (uint8_t r = 0; r < repeats; ++r) {
    if (r) delay(irp::MESSAGE_GAP_MS);
    IrSender.sendRaw(buf, irp::RAW_LEN, irp::CARRIER_KHZ);
  }
}

static bool parse_speed(const char *tok, int8_t *out) {
  if (!tok) return false;
  if (!strcmp(tok, "brake") || !strcmp(tok, "b")) {
    *out = irp::BRAKE;
    return true;
  }
  char *end;
  long v = strtol(tok, &end, 10);
  if (*end || v < -7 || v > 7) return false;
  *out = (int8_t)v;
  return true;
}

static bool parse_channel(const char *tok, uint8_t *out) {
  if (!tok || tok[1] || tok[0] < '1' || tok[0] > '4') return false;
  *out = (uint8_t)(tok[0] - '1');
  return true;
}

static void handle(char *cmd) {
  char *op = strtok(cmd, " ");
  if (!op) return;
  char *a1 = strtok(NULL, " "), *a2 = strtok(NULL, " "), *a3 = strtok(NULL, " ");
  uint8_t ch;
  int8_t s1, s2;
  switch (op[0]) {
    case '?':
      Serial.println(F("OK ir-bridge 1"));
      return;
    case 'P':
    case 'p':
      if (!parse_channel(a1, &ch) || !a2 || a2[1] || !strchr("ABab", a2[0]) || !parse_speed(a3, &s1)) break;
      toggle ^= 1;  // a new command flips the toggle bit; its repeats keep it
      send_message(irp::single_pwm(toggle, ch, (a2[0] == 'B' || a2[0] == 'b'), s1));
      Serial.println(F("OK"));
      return;
    case 'C':
    case 'c':
      if (!parse_channel(a1, &ch) || !parse_speed(a2, &s1) || !parse_speed(a3, &s2)) break;
      send_message(irp::combo_pwm(ch, s1, s2));
      Serial.println(F("OK"));
      return;
    case 'N':
    case 'n': {
      long n = a1 ? strtol(a1, NULL, 10) : 0;
      if (n < 1 || n > 10) break;
      repeats = (uint8_t)n;
      Serial.println(F("OK"));
      return;
    }
  }
  Serial.println(F("ERR bad command"));
}

void setup() {
  Serial.begin(115200);
  IrSender.begin(IR_PIN);
  Serial.println(F("OK ir-bridge 1"));
}

void loop() {
  while (Serial.available()) {
    char c = (char)Serial.read();
    if (c == '\r') continue;
    if (c == '\n') {
      line[line_len] = 0;
      handle(line);
      line_len = 0;
    } else if (line_len < sizeof(line) - 1) {
      line[line_len++] = c;
    }
  }
}
