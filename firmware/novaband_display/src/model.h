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
  int height = 170;        // cm, for the step-length estimate
  int alertHr = 190;       // app-configurable ceiling
};

struct Metrics {
  float hr = 64, spo2 = 98, cadence = 0, pace = 0, dist = 0, kcal = 0, load = 0;
  float temp = 0;          // skin temperature, deg C (0 = no sensor)
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
  bool real = false;               // on the device: readings come from sensors only, nothing is simulated
  bool hrOk = false, spo2Ok = false, cadOk = false, tempOk = false;   // valid sensor reading right now
  static constexpr int PPG_N = 160;
  float ppg[PPG_N] = {0};          // ring buffer at PPG_HZ
  static constexpr float PPG_HZ = 50.f;
  int ppgHead = 0;
  uint32_t beats = 0;              // increments on every heartbeat (UI pulses on change)
  float beatPhase = 0;             // 0..1 within the current beat
  int64_t epochOffset = 0;         // unix time = uptime + offset, once the app syncs time
  bool timeValid = false;
  int tzMin = 0;                   // minutes east of UTC from the last sync
  long long clockNow() const { return (long long)t_ + epochOffset; }   // local unix time, same base as the offset

  void update(float dt, float now);
  void start();
  void pause();
  void stop();
  void setRealHr(float hr, float now);
  void setRealSpo2(float v, float now);
  void setRealCadence(float spm, float now);
  void addSteps(uint32_t n);       // real steps from the pedometer (counted only while running)
  void pushPpg(float v);           // one real PPG sample (PPG_HZ)
  void beat() { beats++; }
  int zoneOf(float hr) const;

 private:
  float target_ = 64, wander_ = 0, ppgAcc_ = 0, t_ = 0, realUntil_ = -1, stepAcc_ = 0, realSpo2Until_ = -1, realCadUntil_ = -1;
  uint32_t newSteps_ = 0;
  uint32_t rng_ = 0x9E3779B9u;
  float noise();
  void updateReal(float dt);
};
