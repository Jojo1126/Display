/*
 * Bus Simulator Display - ESP32-S3 Client
 * 
 * Hardware:
 * - ESP32-S3
 * - 4" TFT Display 480x320 (Arduino GFX Library)
 * 
 * Pin Configuration:
 * TFT_SCK   = 12
 * TFT_MOSI  = 11
 * TFT_CS    = 10
 * TFT_DC    = 9
 * TFT_RST   = 8
 * 
 * Features:
 * - WebSocket client for receiving images from server
 * - Fast RGB565 image display
 * - Automatic reconnection
 * - Telemetry data display (gear, speed)
 */

#include <WiFi.h>
#include <WebSocketsClient.h>
#include <Arduino_GFX_Library.h>
#include <ArduinoJson.h>

// ========== CONFIGURATION - ÄNDERN SIE DIESE WERTE ==========

// WiFi Zugangsdaten - HIER IHRE DATEN EINTRAGEN!
const char* ssid = "MeinWLAN";              // Beispiel: "FritzBox7590" oder "TP-Link_Home"
const char* password = "MeinPasswort123";   // Ihr WLAN-Passwort

// WebSocket Server (Backend URL) - BEREITS KONFIGURIERT!
// Diese URL ist bereits richtig eingestellt für Ihr System
const char* ws_host = "bus-telemetry-hud.preview.emergentagent.com";
const uint16_t ws_port = 443;  // 443 für HTTPS/WSS
const char* ws_path = "/ws/esp32";
const bool use_ssl = true;  // true für wss:// (sicher)

// ===========================================================

// TFT Display Pins
#define TFT_SCK   12
#define TFT_MOSI  11
#define TFT_CS    10
#define TFT_DC    9
#define TFT_RST   8

// Display Resolution
#define SCREEN_WIDTH  480
#define SCREEN_HEIGHT 320

// Display buffer size (RGB565: 2 bytes per pixel)
#define BUFFER_SIZE (SCREEN_WIDTH * SCREEN_HEIGHT * 2)

// Create display object
Arduino_DataBus *bus = new Arduino_HWSPI(TFT_DC, TFT_CS, TFT_SCK, TFT_MOSI);
Arduino_GFX *gfx = new Arduino_ILI9341(bus, TFT_RST, 1 /* rotation */, false /* IPS */);

// WebSocket client
WebSocketsClient webSocket;

// State variables
bool isConnected = false;
uint8_t* imageBuffer = nullptr;
size_t imageBufferSize = 0;
bool receivingImage = false;
String currentImageId = "";
int currentGear = 0;
int currentSpeed = 0;

// Function prototypes
void webSocketEvent(WStype_t type, uint8_t * payload, size_t length);
void displayImage(uint8_t* rgbData, size_t dataSize);
void displayConnectionStatus(const char* message);
void displayTelemetry(int gear, int speed);
void drawText(const char* text, int x, int y, uint16_t color, uint8_t size);

void setup() {
  Serial.begin(115200);
  Serial.println("\n\n=================================");
  Serial.println("Bus Simulator Display - ESP32");
  Serial.println("=================================\n");

  // Initialize display
  Serial.println("Initializing display...");
  gfx->begin();
  gfx->fillScreen(BLACK);
  gfx->setRotation(1);  // Landscape mode
  gfx->setTextSize(2);
  gfx->setTextColor(WHITE);
  
  displayConnectionStatus("Starte...");
  delay(1000);

  // Allocate image buffer in PSRAM (if available)
  if (psramFound()) {
    Serial.println("PSRAM found! Using PSRAM for image buffer.");
    imageBuffer = (uint8_t*)ps_malloc(BUFFER_SIZE);
  } else {
    Serial.println("No PSRAM found. Using regular RAM.");
    imageBuffer = (uint8_t*)malloc(BUFFER_SIZE);
  }
  
  if (imageBuffer == nullptr) {
    Serial.println("ERROR: Failed to allocate image buffer!");
    displayConnectionStatus("FEHLER: RAM!");
    while(1) delay(1000);
  }
  Serial.printf("Image buffer allocated: %d bytes\n", BUFFER_SIZE);

  // Connect to WiFi
  Serial.printf("Connecting to WiFi: %s\n", ssid);
  displayConnectionStatus("WiFi verbinden...");
  
  WiFi.begin(ssid, password);
  
  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < 30) {
    delay(500);
    Serial.print(".");
    attempts++;
  }
  
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("\nERROR: WiFi connection failed!");
    displayConnectionStatus("WiFi FEHLER!");
    while(1) delay(1000);
  }
  
  Serial.println("\nWiFi connected!");
  Serial.print("IP Address: ");
  Serial.println(WiFi.localIP());
  
  char ipMsg[50];
  sprintf(ipMsg, "IP: %s", WiFi.localIP().toString().c_str());
  displayConnectionStatus(ipMsg);
  delay(2000);

  // Connect to WebSocket server
  Serial.printf("Connecting to WebSocket: %s:%d%s\n", ws_host, ws_port, ws_path);
  displayConnectionStatus("WebSocket...");
  
  webSocket.beginSSL(ws_host, ws_port, ws_path);
  webSocket.onEvent(webSocketEvent);
  webSocket.setReconnectInterval(5000);
  
  Serial.println("Setup complete!");
}

void loop() {
  webSocket.loop();
  
  // Add small delay to prevent watchdog issues
  delay(10);
}

void webSocketEvent(WStype_t type, uint8_t * payload, size_t length) {
  switch(type) {
    case WStype_DISCONNECTED:
      Serial.println("[WebSocket] Disconnected!");
      isConnected = false;
      displayConnectionStatus("Getrennt");
      break;
      
    case WStype_CONNECTED:
      Serial.printf("[WebSocket] Connected to: %s\n", payload);
      isConnected = true;
      displayConnectionStatus("Verbunden!");
      
      // Send acknowledgment
      webSocket.sendTXT("{\"type\":\"ack\",\"message\":\"ESP32 connected\"}");
      break;
      
    case WStype_TEXT:
      {
        Serial.printf("[WebSocket] Received text: %s\n", payload);
        
        // Parse JSON message
        StaticJsonDocument<512> doc;
        DeserializationError error = deserializeJson(doc, payload, length);
        
        if (error) {
          Serial.printf("JSON parse error: %s\n", error.c_str());
          return;
        }
        
        const char* msgType = doc["type"];
        
        if (strcmp(msgType, "image") == 0) {
          // Image metadata received
          currentImageId = doc["id"].as<String>();
          imageBufferSize = doc["size"];
          receivingImage = true;
          
          Serial.printf("Receiving image: %s (%d bytes)\n", 
                       currentImageId.c_str(), imageBufferSize);
          displayConnectionStatus("Empfange Bild...");
          
        } else if (strcmp(msgType, "telemetry") == 0) {
          // Telemetry data received
          currentGear = doc["gear"];
          currentSpeed = doc["speed"];
          
          Serial.printf("Telemetry: Gear=%d, Speed=%d km/h\n", currentGear, currentSpeed);
          displayTelemetry(currentGear, currentSpeed);
        }
      }
      break;
      
    case WStype_BIN:
      {
        if (receivingImage) {
          Serial.printf("[WebSocket] Received binary data: %d bytes\n", length);
          
          if (length <= BUFFER_SIZE) {
            // Copy to image buffer
            memcpy(imageBuffer, payload, length);
            
            // Display image
            unsigned long startTime = millis();
            displayImage(imageBuffer, length);
            unsigned long duration = millis() - startTime;
            
            Serial.printf("Image displayed in %lu ms\n", duration);
            
            // Send acknowledgment
            char ackMsg[100];
            sprintf(ackMsg, "{\"type\":\"ack\",\"message\":\"Image %s displayed in %lu ms\"}", 
                   currentImageId.c_str(), duration);
            webSocket.sendTXT(ackMsg);
            
            receivingImage = false;
          } else {
            Serial.printf("ERROR: Image too large! Received %d bytes, buffer is %d bytes\n", 
                         length, BUFFER_SIZE);
            displayConnectionStatus("FEHLER: Bild zu gross!");
            receivingImage = false;
          }
        }
      }
      break;
      
    case WStype_ERROR:
      Serial.printf("[WebSocket] Error: %s\n", payload);
      displayConnectionStatus("WebSocket Fehler");
      break;
      
    case WStype_PING:
      Serial.println("[WebSocket] Ping");
      break;
      
    case WStype_PONG:
      Serial.println("[WebSocket] Pong");
      break;
  }
}

void displayImage(uint8_t* rgbData, size_t dataSize) {
  // RGB565 data is already in the correct format for the display
  // Draw directly to screen for maximum speed
  
  gfx->startWrite();
  gfx->setAddrWindow(0, 0, SCREEN_WIDTH, SCREEN_HEIGHT);
  
  // Write RGB565 data directly
  uint16_t* pixels = (uint16_t*)rgbData;
  size_t pixelCount = dataSize / 2;  // RGB565 = 2 bytes per pixel
  
  for (size_t i = 0; i < pixelCount; i++) {
    gfx->writePixel(pixels[i]);
  }
  
  gfx->endWrite();
}

void displayConnectionStatus(const char* message) {
  gfx->fillScreen(BLACK);
  
  // Draw border
  gfx->drawRect(10, 10, SCREEN_WIDTH - 20, SCREEN_HEIGHT - 20, WHITE);
  
  // Draw title
  gfx->setTextSize(3);
  gfx->setTextColor(CYAN);
  int16_t x1, y1;
  uint16_t w, h;
  gfx->getTextBounds("Bus Display", 0, 0, &x1, &y1, &w, &h);
  gfx->setCursor((SCREEN_WIDTH - w) / 2, 60);
  gfx->print("Bus Display");
  
  // Draw message
  gfx->setTextSize(2);
  gfx->setTextColor(WHITE);
  gfx->getTextBounds(message, 0, 0, &x1, &y1, &w, &h);
  gfx->setCursor((SCREEN_WIDTH - w) / 2, 140);
  gfx->print(message);
  
  // Draw connection indicator
  if (isConnected) {
    gfx->fillCircle(SCREEN_WIDTH / 2, 200, 10, GREEN);
    gfx->setTextSize(1);
    gfx->setTextColor(GREEN);
    gfx->setCursor(SCREEN_WIDTH / 2 - 30, 220);
    gfx->print("VERBUNDEN");
  } else {
    gfx->fillCircle(SCREEN_WIDTH / 2, 200, 10, RED);
    gfx->setTextSize(1);
    gfx->setTextColor(RED);
    gfx->setCursor(SCREEN_WIDTH / 2 - 30, 220);
    gfx->print("GETRENNT");
  }
}

void displayTelemetry(int gear, int speed) {
  // This is a simple overlay for telemetry data
  // You can customize this to match your needs
  
  // Draw semi-transparent background bar at bottom
  gfx->fillRect(0, SCREEN_HEIGHT - 60, SCREEN_WIDTH, 60, 0x18E3);
  
  // Draw gear
  gfx->setTextSize(3);
  gfx->setTextColor(YELLOW);
  gfx->setCursor(50, SCREEN_HEIGHT - 45);
  if (gear == 0) {
    gfx->print("N");
  } else {
    gfx->printf("%d", gear);
  }
  
  // Draw speed
  gfx->setTextSize(3);
  gfx->setTextColor(GREEN);
  gfx->setCursor(SCREEN_WIDTH - 150, SCREEN_HEIGHT - 45);
  gfx->printf("%d", speed);
  
  gfx->setTextSize(2);
  gfx->setCursor(SCREEN_WIDTH - 70, SCREEN_HEIGHT - 40);
  gfx->print("km/h");
}

void drawText(const char* text, int x, int y, uint16_t color, uint8_t size) {
  gfx->setTextSize(size);
  gfx->setTextColor(color);
  gfx->setCursor(x, y);
  gfx->print(text);
}
