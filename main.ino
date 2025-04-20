// Demo 4.1 Temperature and Humidity Sensor
// This example shows how to detect temperature and humidity using SHT4X module
// As well as displaying the information on LCD.
#include <WiFi.h>
#include <PubSubClient.h>

#include <Wire.h>  // Arduino IDE built-in
#include <LiquidCrystal_I2C.h>
#include "Adafruit_SHT4x.h"

// Connect the SHT4X sensor to the Arduino board as below.
// SDA - SDA
// SCL - SCL
// GND - GND (H4)
// VIN - VIN (H4)

//for wifi
WiFiClient espClient;
PubSubClient client(espClient);

const char* ssid = "EIA-W311MESH";
const char* password = "42004200";
const char* mqttServer = "ia.ic.polyu.edu.hk";
const int mqttPort = 1883;

// Defining the ports for LCD (I2C).
#define I2C_SDA 21
#define I2C_SCL 22

// Defining ports for LED.
#define RED 13
#define GRN 27
#define BLUE 2

// Defining ports for IR sensor
#define IR  5

// Defining port for light sensor
#define LIGHT_SENSOR_PIN 39 

byte i = 0;
Adafruit_SHT4x sht4 = Adafruit_SHT4x();
LiquidCrystal_I2C lcd(0x27,16,2);

// Custom character for degree symbol.
byte degreeSym[] = {
  B00111,
  B00101,
  B00111,
  B00000,
  B00000,
  B00000,
  B00000,
  B00000
};

void setup() {
  Serial.begin(9600);

  // WiFi
   WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {
    delay(1400);
    Serial.println("Connecting to WiFi...");
  }
  
  Serial.println("Connected to WiFi");
  
  client.setServer(mqttServer, mqttPort);
  
  while(client.connect("arduinoClient") != true){
    delay(1400);
    Serial.println("Connecting to MQTT broker");
  } 
  Serial.println("Connected to MQTT broker");
  

  // Temp
  Wire.begin(I2C_SDA, I2C_SCL, 100000);
  lcd.begin();
  lcd.setCursor(0,0);

  if (!sht4.begin()) {
    
    lcd.print("Can't find SHT4x");
    while (1) delay(1);
  }
  lcd.clear();
  lcd.print("Found SHT4x!");
  lcd.setCursor(0,1);
  lcd.print("Now loading...");

  // You can have 3 different precisions, higher precision takes longer
  sht4.setPrecision(SHT4X_HIGH_PRECISION);

  // You can have 6 different heater settings
  // higher heat and longer times uses more power
  // and reads will take longer too!
  sht4.setHeater(SHT4X_NO_HEATER);  
  delay(5000);

  lcd.clear();
  lcd.createChar(1, degreeSym);

  lcd.setCursor(0,0);
  lcd.print("T:      C ");
  lcd.setCursor(11,0);
  lcd.write(1);
  lcd.setCursor(0,1);
  lcd.print("L: ");

  // IR
  pinMode(IR, INPUT_PULLUP); //IR detection pin
  //Set up the LEDs
  pinMode(RED,OUTPUT);pinMode(GRN,OUTPUT);pinMode(BLUE,OUTPUT);
  digitalWrite(RED,HIGH);digitalWrite(GRN,HIGH);digitalWrite(BLUE,HIGH); // turn off all LEDs

  

}

void loop() {
  // Temp
  sensors_event_t humidity, temp;
  // populate temp and humidity objects with fresh data
  sht4.getEvent(&humidity, &temp); 

  //lcd.setCursor(6,0);
  //lcd.print(temp.temperature);
  //lcd.setCursor(5,1);
  //lcd.print(humidity.relative_humidity);
  
  // IR
  int logic = digitalRead(IR); // 1: no, 0: 
  Serial.println(logic);

  if (logic == 1) {
    digitalWrite(GRN, HIGH); // Light up the green LED
  } else {
    digitalWrite(GRN, LOW); // Turn off the green LED
  }

  // Light
  // reads the input on analog pin (value between 0 and 4095)
  int analogValue = analogRead(LIGHT_SENSOR_PIN);

  //lcd.clear();
  //lcd.setCursor(6,0);
  //lcd.print(analogValue);
  
  Serial.print("Analog Value = ");
  Serial.print(analogValue);   // the raw analog reading

  // We'll have a few threshholds, qualitatively determined
  if (analogValue < 500) {
    Serial.println(" => Dark");
  } 
  else if (analogValue < 1500) {
    Serial.println(" => Dim");
  } 
  else if (analogValue < 2500) {
    Serial.println(" => Light");
  } 
  else if (analogValue < 3500) {
    Serial.println(" => Bright");
  } 
  else {
    Serial.println(" => Very bright"); // 3500-4095
  }

  lcd.setCursor(3,0);
  lcd.print(temp.temperature);
  lcd.setCursor(11,0);
  lcd.print("M: ");
  lcd.setCursor(14,0);
  lcd.print(logic);
  lcd.setCursor(3,1);
  lcd.print(analogValue);
  //lcd.setCursor(3,1);
  //lcd.print(humidity.relative_humidity);
  
  // send data
  char payload[50];
snprintf(payload, sizeof(payload), "{\"temperature\":%.2f,\"occupancy\":%d,\"light\":%d}", temp.temperature, logic, analogValue);  client.publish("sensors/temperature", payload);
  client.loop(); 
  delay(5000);
}