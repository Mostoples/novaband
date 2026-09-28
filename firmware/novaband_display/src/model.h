// Nova-Band — runner state and metrics.
// The T-Display-S3 has no optical sensor of its own, so unless the app sends
// real readings ("hr" command) the model runs a physiological simulation:
// heart rate with first-order kinetics toward an effort-dependent target,
// a PPG pulse wave (systolic peak + dicrotic notch) locked to it, cadence,
// pace, distance, calories and a TRIMP training load. `demo` says which.
#pragma once
#include <stdint.h>

struct Profile {
  char name[20] = "Runner";
  int age = 17;
  int hrMax = 203;         // 220 - age unless the app sends one
  int hrRest = 62;
  int weight = 58;
  int alertHr = 190;       // app-configurable ceiling
};

struct Metrics {
  float hr = 64, spo2 = 98, cadence = 0, pace = 0, dist = 0, kcal = 0, load = 0;
  uint32_t steps = 0;
  float elapsed = 0;       // s, running time
  int readiness = 82, zone = 1, battery = 100;
  bool usbPower = false;
  bool running = false, paused = false;
};

class Model {
 public:
  Profile profile;
  Metrics m;
  bool demo = true;                // false while the app feeds real HR
  static constexpr int PPG_N = 160;
  float ppg[PPG_N] = {0};          // ring buffer at PPG_HZ
  static constexpr float PPG_HZ = 50.f;
  int ppgHead = 0;
  uint32_t beats = 0;              // increments on every heartbeat (UI pulses on change)
  float beatPhase = 0;             // 0..1 within the current beat
  int64_t epochOffset = 0;         // unix time = uptime + offset, once the app syncs time
  bool timeValid = false;

  void update(float dt, float now);
  void start();
  void pause();
  void stop();
  void setRealHr(float hr, float now);
  int zoneOf(float hr) const;

 private:
  float target_ = 64, wander_ = 0, ppgAcc_ = 0, t_ = 0, realUntil_ = -1, stepAcc_ = 0;
  uint32_t rng_ = 0x9E3779B9u;
  float noise();
};
