// =====================================================================================
// IoT Property Risk Monitoring — ESP32 firmware
// -------------------------------------------------------------------------------------
// Implements docs/SPEC.md (Draft v0.3): telemetry JSON schema, four sensors
// (smoke/gas, flame, water leak, motion), pairing flow, offline buffering,
// Wi-Fi handling, motion debounce + occupancy, sensor health/faults.
// =====================================================================================

#include <Arduino.h>
#include <HTTPClient.h>
#include <Preferences.h>
#include <WiFi.h>
#include <time.h>
#include <string.h>
#include <stdio.h>

// ---------------------------------------------------------------------------
// Configuration — [DRAFT: verify and change your values; draft values marked]
// ---------------------------------------------------------------------------

// Wi-Fi credentials
#define WIFI_SSID "YourWiFiSSID"           // [DRAFT] your WiFi SSID
#define WIFI_PASS "YourWiFiPassword"       // [DRAFT] your WiFi password

// Backend (HTTP ingest per docs/SPEC.md §5)
#define BACKEND_HOST "192.168.1.100"       // [DRAFT] backend address
#define BACKEND_PORT 8000
#define INGEST_PATH "/api/v1/ingest/telemetry"
#define BACKEND_USE_TLS 0                   // 1 = use HTTPS instead of HTTP

// Device identity
#define DEVICE_ID_OVERRIDE ""              // [DRAFT] fixed device_id; "" = generate one from flash
#define DEVICE_ID_PREFIX "esp32"           // prefix for generated device_id

// GPIO pins — [DRAFT: verify against your wiring]
#define PIN_SMOKE_GAS 34                   // analog input — smoke/gas sensor
#define PIN_GAS 35                         // analog input — gas sensor
#define PIN_FLAME 4                        // digital input — flame sensor
#define WATER_PIN 5                        // digital input — water leak sensor
#define PIN_MOTION 12                      // digital input — motion (PIR) sensor
#define BATTERY_ENABLED 1                  // 0 = omit battery_pct
#define BATTERY_PIN 36                     // ADC pin — battery voltage divider
#define WATER_LEAK_ANALOG_PIN -1           // [DRAFT] set >= 0 to read analog level 0-100 instead of digital

#define ADC_FULL_SCALE 4095                // ESP32 12-bit ADC range

// Smoke/gas calibration — [DRAFT: calibrate against sensor datasheets]
#define SMOKE_GAS_WARMUP_MS 300000UL       // MQ sensors need burn-in before trusting readings
#define SMOKE_GAS_PPM_FULL_SCALE 1500.0    // ppm at ADC full scale
#define GAS_PPM_FULL_SCALE 600.0           // ppm at ADC full scale (CO-ish sensor)

// Polarity of active inputs (flip if sensors are active-low)
#define FLAME_ACTIVE_HIGH 1
#define WATER_LEAK_ACTIVE_HIGH 1
#define MOTION_ACTIVE_HIGH 1

// Motion debounce / occupancy (docs/SPEC.md §2.6)
#define MOTION_SAMPLE_MS 50                 // sample PIR frequently; latch events for telemetry
#define MOTION_DEBOUNCE_MS 200
#define OCCUPANCY_TIMEOUT_MS 60000UL       // occupancy expires 60 s after motion

// Telemetry cadence / offline buffering
#define TELEMETRY_INTERVAL_MS 5000
#define PAIR_STATUS_POLL_MS 5000
#define PAIRING_RETRY_MS 15000UL          // backoff after pairing errors
#define MAX_PENDING_BUFFER 64

// ---------------------------------------------------------------------------
// State
// ---------------------------------------------------------------------------

Preferences prefs;

String deviceId;
String deviceToken;    // long-lived Bearer credential for ingest (issued at pairing)
String pairingToken;   // short-lived pairing token while pairing
unsigned long sequence = 0;

bool wifiConnected = false;
int rssiDbm = 0;

float smokePpm = 0.0;
float gasPpm = 0.0;
bool flameDetected = false;
bool waterDetected = false;
int waterLevel = 0;
bool motionEvent = false;       // debounced motion event included in this telemetry
bool motionLatched = false;     // a motion event occurred since the last telemetry
bool motionRawActive = false;   // PIR currently reads active (for occupancy)
String systemMode = "unarmed";   // current system mode: unarmed / armed / armed_away
int batteryPct = -1;

unsigned long lastReadMs = 0;
unsigned long lastPairingPollMs = 0;
unsigned long pairingRetryAtMs = 0;   // backoff after pairing errors (e.g. 401/429)
unsigned long lastModePollMs = 0;
unsigned long lastMotionSampleMs = 0;
unsigned long smokeWarmupEndMs = 0;
unsigned long motionLastEventMs = 0;

struct BufferEntry {
  unsigned long sequence;
  String payload;
};
BufferEntry pendingBuffer[MAX_PENDING_BUFFER];
int pendingCount = 0;

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

static String randomHexString(int length) {
  static const char HEX_CHARS[] = "0123456789abcdef";
  char buf[64];
  int n = length;
  if (n >= (int)sizeof(buf)) n = (int)sizeof(buf) - 1;
  for (int i = 0; i < n; i++) buf[i] = HEX_CHARS[random(16)];
  buf[n] = 0;
  return String(buf);
}

static String fmtFloat(float v) {
  char buf[16];
  snprintf(buf, sizeof(buf), "%.2f", v);
  return String(buf);
}

static bool timeValid() {
  time_t now = time(nullptr);
  struct tm* info = gmtime(&now);
  return info && info->tm_year >= 120;  // >= 2020
}

static String formatTimestamp() {
  time_t now = time(nullptr);
  struct tm* info = gmtime(&now);
  if (!info) return String("null");
  char buf[32];
  strftime(buf, sizeof(buf), "%Y-%m-%dT%H:%M:%SZ", info);
  return String(buf);
}

static void appendFault(String& json, const char* fault, bool& first) {
  if (!first) json += ",";
  json += "\""; json += fault; json += "\"";
  first = false;
}

// Extract a string value for "key" from a small JSON object ("key":"value"); "" if absent.
static String jsonStringField(const String& json, const String& key) {
  String marker;
  marker += "\""; marker += key; marker += "\"";
  int i = json.indexOf(marker);
  if (i < 0) return "";
  i += marker.length();
  int colon = json.indexOf(':', i);
  if (colon < 0) return "";
  int start = json.indexOf('"', colon + 1);
  if (start < 0) return "";
  int end = json.indexOf('"', start + 1);
  if (end < 0) return "";
  return json.substring(start + 1, end);
}

static String backendUrl(const String& path, bool useTls) {
  String url;
  url += useTls ? "https://" : "http://";
  url += BACKEND_HOST;
  url += ":";
  url += String(BACKEND_PORT);
  url += path;
  return url;
}

// Minimal REST helper: method is "GET" or "POST"; bearer may be empty.
static int doRequest(const String& method, const String& path, const String& bearer,
                     const String& body, String& responseOut) {
  if (!wifiConnected) return -1;  // never block the main loop on a dead network
  HTTPClient http;
  http.setTimeout(5000);
#if BACKEND_USE_TLS
  http.begin(backendUrl(path, true));
  http.setInsecure();
#else
  http.begin(backendUrl(path, false));
#endif
  if (!bearer.isEmpty()) {
    String auth;
    auth += "Bearer ";
    auth += bearer;
    http.addHeader("Authorization", auth);
  }
  http.addHeader("Content-Type", "application/json");
  int code;
  if (method == "POST") {
    code = http.sendRequest("POST", body);
  } else {
    code = http.GET();
  }
  responseOut = http.getString();
  http.end();
  return code;
}

// ---------------------------------------------------------------------------
// Sensors
// ---------------------------------------------------------------------------

static float smokePpmFromAdc(int raw) {
  if (raw <= 0) return 0.0;
  return SMOKE_GAS_PPM_FULL_SCALE * raw / (float)ADC_FULL_SCALE;  // [DRAFT linear calibration]
}

static float gasPpmFromAdc(int raw) {
  if (raw <= 0) return 0.0;
  return GAS_PPM_FULL_SCALE * raw / (float)ADC_FULL_SCALE;        // [DRAFT linear calibration]
}

static bool smokeWarmupActive() {
  return millis() < smokeWarmupEndMs;
}

static bool deviceHasFaults() {
  return false;  // extend when sensors add fault conditions
}

static const char* deviceHealth() {
  if (!wifiConnected) return "disconnected";
  if (smokeWarmupActive()) return "degraded";
  if (deviceHasFaults()) return "fault";
  return "ok";
}

static void readSensors() {
  rssiDbm = wifiConnected ? WiFi.RSSI() : 0;

  smokePpm = smokePpmFromAdc(analogRead(PIN_SMOKE_GAS));
  gasPpm = gasPpmFromAdc(analogRead(PIN_GAS));
  flameDetected = digitalRead(PIN_FLAME) == (FLAME_ACTIVE_HIGH ? HIGH : LOW);

#if WATER_LEAK_ANALOG_PIN >= 0
  long rawLevel = map(analogRead(WATER_LEAK_ANALOG_PIN), 0, ADC_FULL_SCALE, 0, 100);
  waterLevel = (int)constrain(rawLevel, 0, 100);
  waterDetected = waterLevel > 0;
#else
  bool raw = digitalRead(WATER_PIN) == (WATER_LEAK_ACTIVE_HIGH ? HIGH : LOW);
  waterDetected = raw;
  // [DRAFT binary scale] a detected digital leak reports the ladder's minimum
  // non-zero level (SPEC §2: warning >= 1 — any detection); analog sensors
  // (WATER_LEAK_ANALOG_PIN >= 0) report the full 0–100 scale.
  waterLevel = raw ? 1 : 0;
#endif
}

static void readBattery() {
#if BATTERY_ENABLED
  int raw = analogRead(BATTERY_PIN);
  batteryPct = raw > 0 ? (int)constrain(map(raw, 0, ADC_FULL_SCALE, 0, 100), 0, 100) : -1;
#else
  batteryPct = -1;
#endif
}

// Sample the PIR often (not just once per telemetry interval) and latch rising
// edges so short motion events are still reported.
static void sampleMotion() {
  unsigned long now = millis();
  if (now - lastMotionSampleMs < MOTION_SAMPLE_MS) return;
  lastMotionSampleMs = now;
  bool raw = digitalRead(PIN_MOTION) == (MOTION_ACTIVE_HIGH ? HIGH : LOW);
  if (raw && !motionRawActive && (motionLastEventMs == 0 || now - motionLastEventMs >= MOTION_DEBOUNCE_MS)) {
    motionLatched = true;
    motionLastEventMs = now;
  }
  motionRawActive = raw;
}

// Move the latched event into the next telemetry payload.
static void captureMotionEvent() {
  motionEvent = motionLatched;
  motionLatched = false;
}

static bool occupancyActive() {
  if (motionRawActive) return true;
  return motionLastEventMs != 0 && (millis() - motionLastEventMs) < OCCUPANCY_TIMEOUT_MS;
}

// ---------------------------------------------------------------------------
// Telemetry
// ---------------------------------------------------------------------------

static String buildTelemetry() {
  ++sequence;
  prefs.putULong("last_sequence", sequence);

  String json;
  json.reserve(384);
  json += "{";
  json += "\"device_id\":\""; json += deviceId; json += "\",";
  json += "\"timestamp\":";
  if (timeValid()) {
    json += "\""; json += formatTimestamp(); json += "\"";
  } else {
    json += "null";
  }
  json += ",\"sequence\":"; json += String(sequence);
#if BATTERY_ENABLED
  json += ",\"battery_pct\":";
  json += (batteryPct >= 0) ? String(batteryPct) : String("null");
#else
  json += ",\"battery_pct\":null";
#endif
  json += ",\"rssi_dbm\":";
  json += (wifiConnected && rssiDbm != 0) ? String(rssiDbm) : String("null");
  json += ",\"device_health\":\""; json += deviceHealth(); json += "\"";
  json += ",\"armed_mode\":\""; json += systemMode; json += "\"";
  json += ",\"faults\":[";
  bool first = true;
  if (smokeWarmupActive()) appendFault(json, "smoke_gas_warmup", first);
  json += "]";
  json += ",\"sensors\":{";
  json += "\"smoke_gas\":{\"smoke_ppm\":"; json += fmtFloat(smokePpm);
  json += ",\"gas_ppm\":"; json += fmtFloat(gasPpm); json += "},";
  json += "\"flame\":{\"detected\":"; json += flameDetected ? String("true") : String("false"); json += "},";
  json += "\"water_leak\":{\"detected\":"; json += waterDetected ? String("true") : String("false");
  json += ",\"level\":"; json += String(waterLevel); json += "},";
  json += "\"motion\":{\"motion_detected\":"; json += motionEvent ? String("true") : String("false");
  json += ",\"occupancy\":"; json += occupancyActive() ? String("true") : String("false");
  json += "}";
  json += "}}";
  return json;
}

// ---------------------------------------------------------------------------
// Publishing + offline buffering
// ---------------------------------------------------------------------------

static void queuePending(const String& payload) {
  if (pendingCount >= MAX_PENDING_BUFFER) {
    Serial.print("[Telemetry] buffer full, dropping seq="); Serial.println(sequence);
    return;
  }
  pendingBuffer[pendingCount].sequence = sequence;
  pendingBuffer[pendingCount].payload = payload;
  pendingCount++;
  Serial.print("[Telemetry] queued (offline) seq="); Serial.println(sequence);
}

static void flushPending() {
  if (!wifiConnected || deviceToken.isEmpty()) return;
  while (pendingCount > 0) {
    String response;
    int code = doRequest("POST", INGEST_PATH, deviceToken, pendingBuffer[0].payload, response);
    if (code >= 200 && code < 300) {
      Serial.print("[Telemetry] flushed seq="); Serial.println(pendingBuffer[0].sequence);
      for (int j = 0; j < pendingCount - 1; j++) pendingBuffer[j] = pendingBuffer[j + 1];
      pendingBuffer[pendingCount - 1] = BufferEntry();
      pendingCount--;
    } else {
      Serial.println("[Telemetry] flush failed, will retry");
      break;
    }
  }
}

static void publishTelemetry() {
  if (deviceToken.isEmpty()) return;  // not paired yet
  String json = buildTelemetry();
  if (!wifiConnected) {
    queuePending(json);
    return;
  }
  String response;
  int code = doRequest("POST", INGEST_PATH, deviceToken, json, response);
  if (code >= 200 && code < 300) {
    // FastAPI serializes as {"accepted": false, ...} (space after colon).
    if (response.indexOf("\"accepted\": false") >= 0) {
      Serial.print("[Telemetry] backend rejected (stale) seq="); Serial.println(sequence);
    } else {
      Serial.print("[Telemetry] published seq="); Serial.println(sequence);
    }
    flushPending();
  } else {
    queuePending(json);
  }
}

// ---------------------------------------------------------------------------
// Wi-Fi handling
// ---------------------------------------------------------------------------

static void handleNetwork() {
  bool connected = (WiFi.status() == WL_CONNECTED);
  if (connected && !wifiConnected) {
    wifiConnected = true;
    Serial.println("[WiFi] connected");
    configTime(0, 0, "pool.ntp.org");  // [DRAFT] sync NTP (gmtOffset_sec=0 → UTC)
    flushPending();
  } else if (!connected && wifiConnected) {
    wifiConnected = false;
    Serial.println("[WiFi] disconnected");
  }
}

// ---------------------------------------------------------------------------
// Pairing
// ---------------------------------------------------------------------------

static String pairStartPath() {
  String p;
  p += "/api/v1/devices/"; p += deviceId; p += "/pair-start";
  return p;
}

static String pairStatusPath() {
  String p;
  p += "/api/v1/devices/"; p += deviceId; p += "/pair-status";
  return p;
}

static void startPairing() {
  // The pairing token is issued by the backend (pair-start response); poll
  // pair-status with that exact token until the mobile app claims it. Never
  // invent a token locally — the backend would not recognise it.
  String response;
  int code = doRequest("POST", pairStartPath(), "", "", response);
  String token = jsonStringField(response, "token");
  if (code < 200 || code >= 300 || token.isEmpty()) {
    Serial.print("[Pairing] pair-start failed (code="); Serial.print(code);
    Serial.println("); will retry");
    pairingRetryAtMs = millis() + PAIRING_RETRY_MS;
    return;
  }
  pairingToken = token;
  prefs.putString("pairing_token", pairingToken);
  Serial.print("[Pairing] pair-start code="); Serial.print(code);
  Serial.println(" — scan the QR shown in the mobile app to complete pairing");
}

static void handlePairing() {
  if (!wifiConnected) return;
  unsigned long now = millis();
  if (now < pairingRetryAtMs) return;
  if (now - lastPairingPollMs < PAIR_STATUS_POLL_MS) return;
  lastPairingPollMs = now;
  if (!pairingToken.isEmpty()) {
    String response;
    int code = doRequest("GET", pairStatusPath(), pairingToken, "", response);
    if (code == 401) {
      // Expired/unrecognised pairing token (e.g. device was offline past the
      // TTL): drop it and start a fresh pairing session after a short backoff.
      Serial.println("[Pairing] pairing token rejected — starting a new session");
      pairingToken = "";
      prefs.putString("pairing_token", "");
      pairingRetryAtMs = now + PAIRING_RETRY_MS;
      return;
    }
    if (code >= 200 && code < 300) {
      String status = jsonStringField(response, "status");
      if (status == "active") {
        String dt = jsonStringField(response, "device_token");
        if (!dt.isEmpty()) {
          deviceToken = dt;
          pairingToken = "";
          prefs.putString("device_token", deviceToken);
          prefs.putString("pairing_token", "");
          Serial.println("[Pairing] device paired — device_token issued");
        }
      }
    }
    return;
  }
  if (deviceToken.isEmpty()) startPairing();
}

static String modePath() {
  String p;
  p += "/api/v1/devices/"; p += deviceId; p += "/mode";
  return p;
}

// Sync system mode down from the backend (SPEC §4 — system mode endpoints).
static void pollSystemMode() {
  if (!wifiConnected || deviceToken.isEmpty()) return;
  unsigned long now = millis();
  if (now - lastModePollMs < TELEMETRY_INTERVAL_MS) return;
  lastModePollMs = now;
  String response;
  int code = doRequest("GET", modePath(), deviceToken, "", response);
  if (code < 200 || code >= 300) return;
  String m = jsonStringField(response, "mode");
  if (m != "unarmed" && m != "armed" && m != "armed_away") return;  // unarmed
  if (m != systemMode) {
    systemMode = m;
    prefs.putString("system_mode", systemMode);
    Serial.print("[Mode] "); Serial.println(systemMode);
  }
}

// ---------------------------------------------------------------------------
// Arduino lifecycle
// ---------------------------------------------------------------------------

void setup() {
  Serial.begin(115200);
  Serial.println();
  Serial.println("[Boot] IoT Property Risk Firmware (draft)");

  pinMode(PIN_SMOKE_GAS, INPUT);
  pinMode(PIN_GAS, INPUT);
  analogReadResolution(12);  // [DRAFT] match ADC_FULL_SCALE used by readSensors/readBattery
#if WATER_LEAK_ANALOG_PIN >= 0
  pinMode(WATER_LEAK_ANALOG_PIN, INPUT);
#else
  pinMode(WATER_PIN, INPUT);
#endif
  pinMode(PIN_FLAME, INPUT);
  pinMode(PIN_MOTION, INPUT);
#if BATTERY_ENABLED
  pinMode(BATTERY_PIN, INPUT);
#endif

  WiFi.begin(WIFI_SSID, WIFI_PASS);

  prefs.begin("iotprm", false);

  if (strlen(DEVICE_ID_OVERRIDE) > 0) {
    deviceId = String(DEVICE_ID_OVERRIDE);
  } else {
    deviceId = prefs.getString("device_id", "");
    if (deviceId.isEmpty()) {
      deviceId = String(DEVICE_ID_PREFIX);
      deviceId += "-";
      deviceId += randomHexString(20);
    }
  }
  prefs.putString("device_id", deviceId);

  deviceToken = prefs.getString("device_token", "");
  pairingToken = prefs.getString("pairing_token", "");
  if (!deviceToken.isEmpty() && !pairingToken.isEmpty()) {
    // Already paired: a leftover pairing token is stale and would block telemetry.
    pairingToken = "";
    prefs.putString("pairing_token", "");
  }
  sequence = prefs.getULong("last_sequence", 0);
  systemMode = prefs.getString("system_mode", "unarmed");
  if (systemMode != "unarmed" && systemMode != "armed" && systemMode != "armed_away") systemMode = "unarmed";
  prefs.putString("system_mode", systemMode);

  smokeWarmupEndMs = millis() + SMOKE_GAS_WARMUP_MS;
  lastMotionSampleMs = millis();
  lastReadMs = millis();

  Serial.print("[Boot] device_id="); Serial.println(deviceId);
  if (deviceToken.isEmpty()) Serial.println("[Boot] awaiting pairing");
}

void loop() {
  handleNetwork();
  sampleMotion();
  handlePairing();
  pollSystemMode();

  unsigned long now = millis();
  if (now - lastReadMs >= TELEMETRY_INTERVAL_MS) {
    lastReadMs = now;
    captureMotionEvent();
    readSensors();
    readBattery();
    publishTelemetry();
  }
}
