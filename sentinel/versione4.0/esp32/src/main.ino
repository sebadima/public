#include <WiFi.h>
#include <HTTPClient.h>
#include <Wire.h>
#include "RTClib.h"

const char* ssid = "NOME_DELLA_RETE_WIFI";
const char* password = "PASSWORD_DELLA_RETE_WIFI";
const char* serverUrl = "http://192.168.1.153:5040/ingest";

RTC_DS3231 rtc;
unsigned long lastMillis = 0;
const long interval = 15000; 

void setup() {
    Serial.begin(115200);
    Wire.begin(21, 22);
    if (!rtc.begin()) {
        Serial.println("[CRITICAL] RTC_NOT_FOUND");
        while (1);
    }
    WiFi.begin(ssid, password);
    Serial.println("[SYSTEM] START_MONITORING");
}

void loop() {
    if (millis() - lastMillis >= interval) {
        lastMillis = millis();

        DateTime now = rtc.now();
        float t1 = -18.0 + (random(-100, 100) / 100.0);
        float t2 = 14.0 + (random(-100, 100) / 100.0);
        float hum = 80.0 + (random(-50, 50) / 10.0);
        float pres = 1013.25 + (random(-100, 100) / 100.0);

        char timestamp[20];
        sprintf(timestamp, "%04d-%02d-%02d %02d:%02d:%02d", now.year(), now.month(), now.day(), now.hour(), now.minute(), now.second());
        
        Serial.print("> DATA_LOG: ");
        Serial.print(timestamp);
        Serial.print(" | T1: "); Serial.print(t1);
        Serial.print(" | T2: "); Serial.print(t2);
        Serial.print(" | HUM: "); Serial.print(hum);
        Serial.print(" | PRES: "); Serial.println(pres);

        // 3. INVIO A FLASK (Se WiFi disponibile)
        if (WiFi.status() == WL_CONNECTED) {
            HTTPClient http;
            http.begin(serverUrl);
            http.addHeader("Content-Type", "application/json");

            String json = "{\"timestamp\":\"" + String(timestamp) + "\",";
            json += "\"t1\":" + String(t1, 2) + ",";
            json += "\"t2\":" + String(t2, 2) + ",";
            json += "\"hum\":" + String(hum, 2) + ",";
            json += "\"pres\":" + String(pres, 2) + "}";

            int code = http.POST(json);
            Serial.printf("[NETWORK] SEND_STATUS: HTTP_%d\n", code);
            http.end();
        } else {
            Serial.println("[NETWORK] OFFLINE - DATA_NOT_SENT");
        }
        Serial.println("------------------------------------------------------------------");
    }
}

