/*
 * Bus Simulator Display - ESP32-S3 Client (USB Serial - CACHED VERSION)
 * 
 * Hardware:
 * - ESP32-S3 with PSRAM
 * - 4" TFT Display 480x320 (ILI9488 Driver)
 * 
 * Features:
 * - Image caching in PSRAM (up to 8 images)
 * - Instant image switching (<100ms)
 * - USB Serial communication
 * 
 * Protocol:
 * - Cache image: "CACHE:[slot]:[size]\n" + RGB565 data
 * - Show image: "SHOW:[slot]\n"
 * - Clear cache: "CLEAR\n"
 * - Status: "STATUS\n"
 */

#include <Arduino_GFX_Library.h>

// Color definitions (RGB565)
#define BLACK   0x0000
#define WHITE   0xFFFF
#define RED     0xF800
#define GREEN   0x07E0
#define BLUE    0x001F
#define CYAN    0x07FF
#define MAGENTA 0xF81F
#define YELLOW  0xFFE0
#define ORANGE  0xFC00

// TFT Display Pins
#define TFT_SCK   12
#define TFT_MOSI  11
#define TFT_CS    10
#define TFT_DC    9
#define TFT_RST   8

// Display Resolution
#define SCREEN_WIDTH  480
#define SCREEN_HEIGHT 320

// Image cache settings
#define MAX_CACHED_IMAGES 8
#define IMAGE_SIZE (SCREEN_WIDTH * SCREEN_HEIGHT * 2)  // 307200 bytes per image

// Create display object
Arduino_DataBus *bus = new Arduino_HWSPI(TFT_DC, TFT_CS, TFT_SCK, TFT_MOSI);
Arduino_GFX *gfx = new Arduino_ILI9488(bus, TFT_RST, 0 /* rotation */, false /* IPS */);

// Image cache in PSRAM
uint8_t* imageCache[MAX_CACHED_IMAGES] = {nullptr};
bool cacheSlotUsed[MAX_CACHED_IMAGES] = {false};
int currentDisplayedSlot = -1;

// Temporary buffer for receiving
uint8_t* receiveBuffer = nullptr;

// State variables
bool receivingImage = false;
size_t expectedSize = 0;
size_t receivedBytes = 0;
int targetCacheSlot = -1;
unsigned long lastStatusTime = 0;

// Function prototypes
void processSerialCommand();
void displayCachedImage(int slot);
void cacheImage(int slot, uint8_t* data, size_t size);
void clearCache();
void printStatus();
void displayWelcomeScreen();
void sendAck();

void setup() {
  Serial.begin(921600);  // Increased from 115200 to 921600 for faster transfer!
  Serial.setRxBufferSize(16384);  // Increase RX buffer to 16KB for faster reception
  delay(1000);
  
  Serial.println("\n\n=================================");
  Serial.println("Bus Simulator Display - ESP32");
  Serial.println("CACHED VERSION - Ultra Fast!");
  Serial.println("ILI9488 Standard Driver");
  Serial.println("=================================\n");

  // Initialize display
  Serial.println("Initializing display...");
  gfx->begin();
  gfx->fillScreen(BLACK);
  gfx->setRotation(3);  // Landscape
  
  displayWelcomeScreen();
  
  // Check PSRAM
  if (!psramFound()) {
    Serial.println("ERROR: PSRAM not found! Caching requires PSRAM.");
    gfx->fillScreen(RED);
    gfx->setTextColor(WHITE);
    gfx->setTextSize(2);
    gfx->setCursor(100, 150);
    gfx->print("ERROR: NO PSRAM!");
    while(1) delay(1000);
  }
  
  Serial.println("PSRAM found! Initializing cache...");
  
  // Allocate receive buffer in PSRAM
  receiveBuffer = (uint8_t*)ps_malloc(IMAGE_SIZE);
  if (receiveBuffer == nullptr) {
    Serial.println("ERROR: Failed to allocate receive buffer!");
    while(1) delay(1000);
  }
  
  Serial.printf("Receive buffer allocated: %d bytes\n", IMAGE_SIZE);
  Serial.printf("Cache slots available: %d\n", MAX_CACHED_IMAGES);
  Serial.printf("Total cache capacity: %d MB\n", (IMAGE_SIZE * MAX_CACHED_IMAGES) / (1024 * 1024));
  Serial.println("\nReady for image caching!");
  Serial.println("Commands:");
  Serial.println("  CACHE:[slot]:[size]  - Cache image (slot 0-7)");
  Serial.println("  SHOW:[slot]          - Display cached image");
  Serial.println("  CLEAR                - Clear all cache");
  Serial.println("  STATUS               - Show cache status");
  Serial.println("ACK");
  
  lastStatusTime = millis();
}

void loop() {
  if (Serial.available()) {
    processSerialCommand();
  }
  
  // Periodic status update
  if (millis() - lastStatusTime > 30000) {
    Serial.println("STATUS: Ready");
    lastStatusTime = millis();
  }
  
  delay(10);
}

void processSerialCommand() {
  String line = Serial.readStringUntil('\n');
  line.trim();
  
  if (line.length() == 0) return;
  
  Serial.printf(">>> Received: %s\n", line.c_str());
  
  if (line.startsWith("CACHE:")) {
    // Cache image command: CACHE:[slot]:[size]
    int firstColon = line.indexOf(':', 6);
    if (firstColon > 0) {
      int slot = line.substring(6, firstColon).toInt();
      expectedSize = line.substring(firstColon + 1).toInt();
      
      if (slot < 0 || slot >= MAX_CACHED_IMAGES) {
        Serial.printf("ERROR: Invalid slot %d (must be 0-%d)\n", slot, MAX_CACHED_IMAGES - 1);
        return;
      }
      
      if (expectedSize != IMAGE_SIZE) {
        Serial.printf("ERROR: Invalid size %d (expected %d)\n", expectedSize, IMAGE_SIZE);
        return;
      }
      
      Serial.printf(">>> Caching to slot %d: %d bytes\n", slot, expectedSize);
      targetCacheSlot = slot;
      receivingImage = true;
      receivedBytes = 0;
      
      sendAck();
      
      // Receive image data with MAXIMUM speed
      unsigned long startTime = millis();
      unsigned long timeoutTime = startTime + 30000;
      
      // Read in LARGE blocks for maximum speed
      while (receivedBytes < expectedSize && millis() < timeoutTime) {
        size_t available = Serial.available();
        if (available > 0) {
          size_t toRead = min(available, expectedSize - receivedBytes);
          
          // Read as much as possible at once
          size_t actualRead = Serial.readBytes(receiveBuffer + receivedBytes, toRead);
          receivedBytes += actualRead;
          
          // Progress update only every 50KB for speed
          if (receivedBytes % 51200 == 0 || receivedBytes == expectedSize) {
            int progress = (receivedBytes * 100) / expectedSize;
            Serial.printf(">>> %d%% ", progress);
          }
        }
        // NO YIELD, NO DELAY - maximum speed!
      }
      Serial.println();  // Newline after progress
      
      if (receivedBytes == expectedSize) {
        unsigned long duration = millis() - startTime;
        Serial.printf(">>> Image received in %lu ms\n", duration);
        
        // Store in cache
        cacheImage(targetCacheSlot, receiveBuffer, receivedBytes);
        
        Serial.printf(">>> Image cached to slot %d\n", targetCacheSlot);
        Serial.println("CACHED_OK");
      } else {
        Serial.printf("ERROR: Timeout! Received %d of %d bytes\n", receivedBytes, expectedSize);
      }
      
      receivingImage = false;
      targetCacheSlot = -1;
      
    }
    
  } else if (line.startsWith("SHOW:")) {
    // Show cached image: SHOW:[slot] or SHOW:[slot]:[gear]:[speed]
    int firstColon = line.indexOf(':', 5);
    
    if (firstColon > 0) {
      // SHOW with telemetry: SHOW:[slot]:[gear]:[speed]
      int slot = line.substring(5, firstColon).toInt();
      int secondColon = line.indexOf(':', firstColon + 1);
      
      if (secondColon > 0) {
        int gear = line.substring(firstColon + 1, secondColon).toInt();
        int speed = line.substring(secondColon + 1).toInt();
        
        if (slot < 0 || slot >= MAX_CACHED_IMAGES) {
          Serial.printf("ERROR: Invalid slot %d\n", slot);
          return;
        }
        
        if (!cacheSlotUsed[slot]) {
          Serial.printf("ERROR: Slot %d is empty\n", slot);
          return;
        }
        
        Serial.printf(">>> Displaying slot %d with telemetry: Gear=%d, Speed=%d\n", slot, gear, speed);
        unsigned long startTime = millis();
        
        displayCachedImageWithTelemetry(slot, gear, speed);
        
        unsigned long duration = millis() - startTime;
        Serial.printf(">>> Display with telemetry took %lu ms\n", duration);
        Serial.println("SHOW_OK");
      } else {
        // SHOW without telemetry
        int slot = line.substring(5, firstColon).toInt();
        
        if (slot < 0 || slot >= MAX_CACHED_IMAGES) {
          Serial.printf("ERROR: Invalid slot %d\n", slot);
          return;
        }
        
        if (!cacheSlotUsed[slot]) {
          Serial.printf("ERROR: Slot %d is empty\n", slot);
          return;
        }
        
        Serial.printf(">>> Displaying cached image from slot %d\n", slot);
        unsigned long startTime = millis();
        
        displayCachedImage(slot);
        
        unsigned long duration = millis() - startTime;
        Serial.printf(">>> Display switch took %lu ms\n", duration);
        Serial.println("SHOW_OK");
      }
    } else {
      // Simple SHOW:[slot]
      int slot = line.substring(5).toInt();
      
      if (slot < 0 || slot >= MAX_CACHED_IMAGES) {
        Serial.printf("ERROR: Invalid slot %d\n", slot);
        return;
      }
      
      if (!cacheSlotUsed[slot]) {
        Serial.printf("ERROR: Slot %d is empty\n", slot);
        return;
      }
      
      Serial.printf(">>> Displaying cached image from slot %d\n", slot);
      unsigned long startTime = millis();
      
      displayCachedImage(slot);
      
      unsigned long duration = millis() - startTime;
      Serial.printf(">>> Display switch took %lu ms\n", duration);
      Serial.println("SHOW_OK");
    }
    
  } else if (line.startsWith("CLEAR")) {
    Serial.println(">>> Clearing cache...");
    clearCache();
    Serial.println("CLEAR_OK");
    
  } else if (line.startsWith("STATUS")) {
    printStatus();
    
  } else {
    Serial.printf("Unknown command: %s\n", line.c_str());
  }
}

void cacheImage(int slot, uint8_t* data, size_t size) {
  // Free old data if slot was used
  if (cacheSlotUsed[slot] && imageCache[slot] != nullptr) {
    free(imageCache[slot]);
    imageCache[slot] = nullptr;
  }
  
  // Allocate memory in PSRAM
  imageCache[slot] = (uint8_t*)ps_malloc(size);
  
  if (imageCache[slot] == nullptr) {
    Serial.printf("ERROR: Failed to allocate cache for slot %d\n", slot);
    cacheSlotUsed[slot] = false;
    return;
  }
  
  // Copy data
  memcpy(imageCache[slot], data, size);
  cacheSlotUsed[slot] = true;
  
  Serial.printf("Cache slot %d: %d bytes allocated\n", slot, size);
}

void displayCachedImage(int slot) {
  if (!cacheSlotUsed[slot] || imageCache[slot] == nullptr) {
    Serial.printf("ERROR: Slot %d not available\n", slot);
    return;
  }
  
  // Ultra-fast display from cached data
  gfx->draw16bitRGBBitmap(0, 0, (uint16_t*)imageCache[slot], SCREEN_WIDTH, SCREEN_HEIGHT);
  
  currentDisplayedSlot = slot;
}

void displayCachedImageWithTelemetry(int slot, int gear, int speed) {
  if (!cacheSlotUsed[slot] || imageCache[slot] == nullptr) {
    Serial.printf("ERROR: Slot %d not available\n", slot);
    return;
  }
  
  // Display cached image
  gfx->draw16bitRGBBitmap(0, 0, (uint16_t*)imageCache[slot], SCREEN_WIDTH, SCREEN_HEIGHT);
  
  // Draw numbers in the TOP BAR (upper part of the display)
  // Based on the reference image: numbers should be at the top
  // Display is 480x320, so we scale the positions accordingly
  
  gfx->setTextColor(WHITE);
  gfx->setTextSize(3);  // Large text for visibility
  
  // LEFT: Gear number (approximately 15% from left, near top)
  // Reference: X=90 in ~600px wide → 15% → 72px in 480px
  gfx->setCursor(72, 10);
  if (gear == 0) {
    gfx->print("N");  // Neutral
  } else if (gear == -1) {
    gfx->print("R");  // Reverse
  } else {
    gfx->print(gear);
  }
  
  // RIGHT: Speed number (approximately 75% from left, near top)
  // Reference: X=360 in ~600px wide → 60% → 288px in 480px
  // Adjusted 0.5cm to the right (+25px)
  // Adjust for right-alignment based on digit count
  int speedX = 405;  // Base position for right side (moved right by 25px)
  if (speed < 10) {
    speedX += 0;  // Single digit
  } else if (speed < 100) {
    speedX -= 20;  // Two digits
  } else {
    speedX -= 40;  // Three digits
  }
  
  gfx->setCursor(speedX, 10);
  gfx->print(speed);
  
  currentDisplayedSlot = slot;
}

void clearCache() {
  for (int i = 0; i < MAX_CACHED_IMAGES; i++) {
    if (cacheSlotUsed[i] && imageCache[i] != nullptr) {
      free(imageCache[i]);
      imageCache[i] = nullptr;
      cacheSlotUsed[i] = false;
    }
  }
  currentDisplayedSlot = -1;
  Serial.println("Cache cleared");
}

void printStatus() {
  Serial.println("=== CACHE STATUS ===");
  Serial.printf("PSRAM Total: %d bytes\n", ESP.getPsramSize());
  Serial.printf("PSRAM Free: %d bytes\n", ESP.getFreePsram());
  Serial.printf("Cache slots: %d\n", MAX_CACHED_IMAGES);
  
  int usedSlots = 0;
  for (int i = 0; i < MAX_CACHED_IMAGES; i++) {
    if (cacheSlotUsed[i]) {
      Serial.printf("Slot %d: USED (%d KB)\n", i, IMAGE_SIZE / 1024);
      usedSlots++;
    } else {
      Serial.printf("Slot %d: EMPTY\n", i);
    }
  }
  
  Serial.printf("Total used: %d/%d slots (%d KB)\n", 
               usedSlots, MAX_CACHED_IMAGES, (usedSlots * IMAGE_SIZE) / 1024);
  Serial.printf("Currently displayed: Slot %d\n", currentDisplayedSlot);
  Serial.println("===================");
  Serial.println("STATUS_OK");
}

void displayWelcomeScreen() {
  gfx->fillScreen(0x18E3);
  
  gfx->drawRect(10, 10, SCREEN_WIDTH - 20, SCREEN_HEIGHT - 20, WHITE);
  gfx->drawRect(12, 12, SCREEN_WIDTH - 24, SCREEN_HEIGHT - 24, WHITE);
  
  gfx->setTextSize(4);
  gfx->setTextColor(WHITE);
  gfx->setCursor(80, 60);
  gfx->print("Bus Display");
  
  gfx->setTextSize(2);
  gfx->setTextColor(CYAN);
  gfx->setCursor(120, 120);
  gfx->print("CACHED VERSION");
  
  gfx->setTextSize(1);
  gfx->setTextColor(YELLOW);
  gfx->setCursor(140, 145);
  gfx->print("Ultra-Fast Image Switching");
  
  gfx->setTextSize(2);
  gfx->setTextColor(GREEN);
  gfx->setCursor(70, 190);
  gfx->print("Bilder einmalig laden");
  
  gfx->setTextSize(2);
  gfx->setTextColor(ORANGE);
  gfx->setCursor(60, 220);
  gfx->print("Dann: Wechsel <100ms!");
  
  gfx->fillCircle(SCREEN_WIDTH / 2, 270, 15, GREEN);
  gfx->setTextSize(1);
  gfx->setTextColor(WHITE);
  gfx->setCursor(SCREEN_WIDTH / 2 - 30, 295);
  gfx->print("USB READY");
}

void sendAck() {
  Serial.println("ACK");
}
