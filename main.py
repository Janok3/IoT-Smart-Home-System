import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
import time
import logging
import paho.mqtt.client as mqtt
import json
import requests

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger("SmartHomeAI")

# MQTT Configuration
#MQTT_BROKER = "test.mosquitto.org"  # Change to your MQTT broker address
MQTT_BROKER = "ia.ic.polyu.edu.hk"  # Change to your MQTT broker address
MQTT_PORT = 1883
MQTT_CLIENT_ID = "smart_home_ai_controller"
MQTT_TOPIC_SENSOR = "sensors/temperature"
MQTT_TOPIC_DECISION = "smart_home/ai_decision"

# ThingSpeak Configuration
THINGSPEAK_CHANNEL_ID = "2920063"  # Replace with your ThingSpeak channel ID
THINGSPEAK_API_KEY = "GGQ0VC1TCCWEZ8A8"  # Replace with your ThingSpeak read API key
THINGSPEAK_URL = f"https://api.thingspeak.com/channels/{THINGSPEAK_CHANNEL_ID}/feeds.json"


# Initialize MQTT client
def setup_mqtt():
    client = mqtt.Client(client_id=MQTT_CLIENT_ID, callback_api_version=mqtt.CallbackAPIVersion.VERSION1)
    try:
        client.connect(MQTT_BROKER, MQTT_PORT, 60)
        client.loop_start()
        logger.info(f"Connected to MQTT broker at {MQTT_BROKER}:{MQTT_PORT}")
        return client
    except Exception as e:
        logger.error(f"Failed to connect to MQTT broker: {e}")
        return None



def fetch_training_data_from_thingspeak(results=1000):
    """
    Fetch historical data from ThingSpeak and return as a DataFrame.
    field1=Temperature, field2=Light, field3=Occupancy, field4=lightSwitch.
    """
    url = f"{THINGSPEAK_URL}?api_key={THINGSPEAK_API_KEY}&results={results}"
    try:
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            feeds = data.get("feeds", [])
            temperature = []
            light = []
            occupancy = []
            light_switch = []
            for entry in feeds:
                try:
                    temp = float(entry.get("field1", "nan"))
                    lig = float(entry.get("field2", "nan"))
                    occ = float(entry.get("field3", "nan"))
                    switch = float(entry.get("field4", "nan"))
                    if not (np.isnan(temp) or np.isnan(lig) or np.isnan(occ) or np.isnan(switch)):
                        temperature.append(temp)
                        light.append(lig)
                        occupancy.append(int(occ))
                        light_switch.append(int(switch))
                except Exception as e:
                    logger.warning(f"Skipping entry due to parse error: {e}")
            if len(temperature) == 0:
                logger.error("No valid data fetched from ThingSpeak.")
                return pd.DataFrame(columns=["temperature", "light", "occupancy", "lightSwitch"])
            df = pd.DataFrame({
                "temperature": temperature,
                "light": light,
                "occupancy": occupancy,
                "lightSwitch": light_switch
            })
            logger.info(f"Fetched {len(df)} samples from ThingSpeak for training.")
            return df
        else:
            logger.error(f"Failed to fetch data from ThingSpeak: HTTP {response.status_code}")
            return pd.DataFrame(columns=["temperature", "light", "occupancy", "lightSwitch"])
    except Exception as e:
        logger.error(f"Error fetching data from ThingSpeak: {e}")
        return pd.DataFrame(columns=["temperature", "light", "occupancy", "lightSwitch"])


# Train AI model
def train_model(df):
    X = df[["temperature", "light", "occupancy"]]
    y = df["lightSwitch"]
    model = RandomForestClassifier(n_estimators=100, random_state=42, class_weight="balanced")
    model.fit(X, y)
    logger.info("AI Model trained successfully.")
    return model


# Control lights based on AI prediction
def control_lights(model, temp, light, occupancy, mqtt_client=None):
    prediction = model.predict([[temp, light, occupancy]])
    decision = "ON" if prediction[0] == 1 else "OFF"
    
    if prediction[0] == 1:
        logger.info("🟢 AI Decision: Turn ON Lights")
        # GPIO.output(LIGHT_PIN, True)  # Uncomment for real hardware
    else:
        logger.info("🔴 AI Decision: Turn OFF Lights")
        # GPIO.output(LIGHT_PIN, False)  # Uncomment for real hardware
    
    # Publish to MQTT if client is available
    if mqtt_client:
        publish_to_mqtt(mqtt_client, decision)


# Publish data to MQTT
def publish_to_mqtt(client, decision):
    try:
        # Publish AI decision
        decision_payload = json.dumps({
            "lights": decision,
            "timestamp": time.time()
        })
        client.publish(MQTT_TOPIC_DECISION, decision_payload)
        
        logger.info(f"Data published to MQTT topics: {MQTT_TOPIC_DECISION}")
    except Exception as e:
        logger.error(f"Failed to publish to MQTT: {e}")



def get_sensor_data_from_mqtt(mqtt_client, timeout=5):
    """
    Waits for a message on the MQTT_TOPIC_SENSOR and returns temperature, light, occupancy.
    Returns (None, None, None) if no message is received within the timeout.
    """
    sensor_data = {"temperature": None, "light": None, "occupancy": None}
    event = {"received": False}

    def on_message(client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode())
            sensor_data["temperature"] = float(payload.get("temperature", 0))
            sensor_data["light"] = float(payload.get("light", 0))
            sensor_data["occupancy"] = int(payload.get("occupancy", 0))
            event["received"] = True
            logger.info(f"Received MQTT sensor data: {sensor_data}")
        except Exception as e:
            logger.error(f"Error parsing MQTT sensor data: {e}")

    # Temporarily set the on_message callback
    mqtt_client.subscribe(MQTT_TOPIC_SENSOR)
    mqtt_client.on_message = on_message

    # Wait for a message or timeout
    start_time = time.time()
    while not event["received"] and (time.time() - start_time) < timeout:
        time.sleep(0.1)

    # Optionally, reset the on_message callback if needed
    # mqtt_client.on_message = None

    if event["received"]:
        return sensor_data["temperature"], sensor_data["light"], sensor_data["occupancy"]
    else:
        logger.warning("No MQTT sensor data received within timeout.")
        return None, None, None

# Main loop
if __name__ == "__main__":
    logger.info("Starting Smart Home AI Controller...")
    # Use all available ThingSpeak data for training
    training_df = fetch_training_data_from_thingspeak(results=300)  # or up to 8000
    if training_df.empty:
        logger.error("No training data available. Exiting.")
        exit(1)
    # Log the balance of the lightSwitch column
    logger.info(f"lightSwitch value counts:\n{training_df['lightSwitch'].value_counts()}") # For debugging
    model = train_model(training_df)
    mqtt_client = setup_mqtt()
    
    while True:
        try:
            # Step 1: Get current sensor data
            temp, light, occupancy = get_sensor_data_from_mqtt(mqtt_client)
            if temp is None:
                continue 
            # Step 2: AI makes decision and publish to MQTT
            control_lights(model, temp, light, occupancy, mqtt_client)
            
            # Step 3: Wait before next reading (e.g., 5 seconds)
            time.sleep(0.01)
            
        except KeyboardInterrupt:
            logger.info("Stopping controller...")
            if mqtt_client:
                mqtt_client.loop_stop()
                mqtt_client.disconnect()
                logger.info("MQTT client disconnected")
            break