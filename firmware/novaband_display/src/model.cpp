#include "model.h"

#include <math.h>

static const float TAU = 6.2831853f;

float Model::noise() {             // xorshift -> [-1, 1]
  rng_ ^= rng_ << 13; rng_ ^= rng_ >> 17; rng_ ^= rng_ << 5;
  return (rng_ & 0xFFFF) / 32767.5f - 1.f;
}

int Model::zoneOf(float hr) const {
  float p = hr / profile.hrMax;
  return p < .6f ? 1 : p < .7f ? 2 : p < .8f ? 3 : p < .9f ? 4 : 5;
}

void Model::start() {
  if (!m.running) { m.elapsed = 0; m.dist = 0; m.kcal = 0; m.load = 0; m.steps = 0; m.pace = 380; }
  m.running = true; m.paused = false;
}
void Model::pause() { if (m.running) m.paused = !m.paused; }
void Model::stop() { m.running = false; m.paused = false; }

void Model::setRealHr(float hr, float now) {
  m.hr = hr; demo = false; realUntil_ = now + 5.f;   // falls back to the model 5 s after the last reading
}

void Model::setRealSpo2(float v, float now) { m.spo2 = v; realSpo2Until_ = now + 5.f; }
void Model::setRealCadence(float spm, float now) { m.cadence = spm; realCadUntil_ = now + 3.f; }

void Model::addSteps(uint32_t n) { if (m.running && !m.paused) newSteps_ += n; }

void Model::pushPpg(float v) { ppg[ppgHead] = v; ppgHead = (ppgHead + 1) % PPG_N; }

void Model::update(float dt, float now) {
  t_ = now;
  if (real) { updateReal(dt); return; }
  if (realUntil_ > 0 && now > realUntil_) { demo = true; realUntil_ = -1; }
  bool moving = m.running && !m.paused;

  // --- effort -> heart-rate target (warm-up ramp, then a slow drift with surges)
  wander_ += (noise() * 1.6f - wander_ * 0.05f) * dt;
  if (moving) {
    float warm = fminf(m.elapsed / 240.f, 1.f);
    target_ = 112 + 48 * warm + 6 * sinf(m.elapsed / 55.f) + wander_ * 2.f;
  } else {
    target_ = profile.hrRest + 4 + wander_ * 1.5f + 3 * sinf(now / 23.f);
  }
  if (demo) {
    float tau = target_ > m.hr ? 22.f : 38.f;          // HR rises faster than it recovers
    m.hr += (target_ - m.hr) * (1 - expf(-dt / tau));
  }
  m.zone = zoneOf(m.hr);
  if (now > realSpo2Until_) m.spo2 = 97.6f + 0.6f * sinf(now / 17.f) - (moving ? 0.8f : 0);

  // --- locomotion
  if (moving) {
    m.elapsed += dt;
    if (now > realCadUntil_) m.cadence += ((166 + 5 * sinf(m.elapsed / 40.f) + noise()) - m.cadence) * (1 - expf(-dt / 3.f));
    float pace = 332 - 14 * sinf(m.elapsed / 70.f);   // s per km, ~5:32
    m.pace += (pace - m.pace) * (1 - expf(-dt / 5.f));
    m.dist += dt / fmaxf(m.pace, 150.f);                // guard: pace eases in from the start value
    stepAcc_ += m.cadence / 60.f * dt;
    while (stepAcc_ >= 1) { m.steps++; stepAcc_ -= 1; }
    // Keytel et al. energy expenditure (kJ/min) -> kcal
    float kj = (-55.0969f + 0.6309f * m.hr + 0.1988f * profile.weight + 0.2017f * profile.age) / 4.184f;
    if (kj > 0) m.kcal += kj * dt / 60.f;
    float hrr = (m.hr - profile.hrRest) / (float)(profile.hrMax - profile.hrRest);
    if (hrr > 0) m.load += dt / 60.f * hrr * 0.64f * expf(1.92f * hrr);   // Banister TRIMP
  } else {
    if (now > realCadUntil_) m.cadence += (0 - m.cadence) * (1 - expf(-dt / 1.5f));
  }

  // --- PPG pulse wave, sampled at PPG_HZ, locked to the heart rate
  ppgAcc_ += dt;
  const float step = 1.f / PPG_HZ;
  while (ppgAcc_ >= step) {
    ppgAcc_ -= step;
    beatPhase += m.hr / 60.f * step;
    if (beatPhase >= 1) { beatPhase -= 1; beats++; }
    float p = beatPhase;
    float sys = expf(-powf((p - .16f) / .065f, 2));        // systolic upstroke/peak
    float dic = .38f * expf(-powf((p - .47f) / .085f, 2));  // dicrotic wave after the notch
    float v = sys + dic + .08f * sinf(TAU * .23f * t_) + .025f * noise();
    if (moving) v += .07f * sinf(TAU * m.cadence / 60.f * t_);   // residual motion artefact
    ppg[ppgHead] = v;
    ppgHead = (ppgHead + 1) % PPG_N;
  }
}

// Sensor mode: measured values only. There is no GPS, so distance and pace are estimates from
// the counted steps x step length (0.415 x height) instead.
void Model::updateReal(float dt) {
  bool moving = m.running && !m.paused;
  demo = false;
  m.zone = hrOk ? zoneOf(m.hr) : 1;
  const float stride = 0.00415f * profile.height;            // metres per step
  if (!moving) newSteps_ = 0;
  struct Flush { uint32_t& n; ~Flush() { n = 0; } } flush{newSteps_};
  float speed = cadOk ? m.cadence / 60.f * stride : 0;       // m/s
  m.pace = moving && speed > .5f ? 1000.f / speed : 0;       // s/km
  if (moving) {
    m.elapsed += dt;
    m.steps += newSteps_; m.dist += newSteps_ * stride / 1000.f;   // real counted steps
    if (hrOk) {
      float kj = (-55.0969f + 0.6309f * m.hr + 0.1988f * profile.weight + 0.2017f * profile.age) / 4.184f;
      if (kj > 0) m.kcal += kj * dt / 60.f;
      float hrr = (m.hr - profile.hrRest) / (float)(profile.hrMax - profile.hrRest);
      if (hrr > 0) m.load += dt / 60.f * hrr * 0.64f * expf(1.92f * hrr);
    }
  }
}
