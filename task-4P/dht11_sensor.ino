#include <DHT.h>

#define DHT_PIN 2
#define DHT_TYPE DHT11

DHT dht(DHT_PIN, DHT_TYPE);

void setup() {
  Serial.begin(9600);
  dht.begin();

  delay(2000);

  Serial.println("elapsed_ms,temperature_c,humidity_percent");
}

void loop() {
  float humidity = dht.readHumidity();
  float temperature = dht.readTemperature();

  if (isnan(temperature) || isnan(humidity)) {
    Serial.println("ERROR,DHT11 reading failed");
    delay(2000);
    return;
  }

  Serial.print(millis());
  Serial.print(",");
  Serial.print(temperature, 1);
  Serial.print(",");
  Serial.println(humidity, 1);

  delay(2000);
}
