import hmac
import json
import logging
import os
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen

READY = Path('/tmp/worker-ready')


def unlock_result(teams, topic, payload, callback_url, secret):
    parts = topic.split('/')
    if len(parts) != 3 or parts[0] != 'lab' or parts[2] != 'unlock' or parts[1] not in teams:
        return None
    team = parts[1]
    if not hmac.compare_digest(payload, teams[team]['unlock_code'].encode()):
        return f'{team}: incorrect unlock code. Try again.'
    request = Request(f'{callback_url}/internal/complete/{team}', data=b'',
                      headers={'Authorization': f'Bearer {secret}'}, method='POST')
    try:
        with urlopen(request, timeout=5) as response:
            return response.read().decode().strip()
    except (URLError, TimeoutError, OSError):
        logging.exception('Completion callback failed for %s', team)
        return f'{team}: completion service unavailable; subscribe again and retry.'


def main():
    import paho.mqtt.client as mqtt

    teams = json.loads((Path(os.getenv('FIXTURES_DIR', '/fixtures')) / 'config.json').read_text())['teams']
    secret = os.environ['WORKER_CALLBACK_SECRET']
    callback = os.getenv('CALLBACK_URL', 'http://http:8080')
    READY.unlink(missing_ok=True)
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)

    def connected(client, userdata, flags, reason_code, properties):
        if not reason_code.is_failure:
            client.subscribe([(f'lab/{team}/unlock', 0) for team in teams])

    def subscribed(client, userdata, mid, reason_codes, properties):
        if all(not code.is_failure for code in reason_codes):
            READY.touch()
            logging.info('Ready: subscribed to unlock topics')

    def disconnected(client, userdata, flags, reason_code, properties):
        READY.unlink(missing_ok=True)

    def message(client, userdata, message):
        # A retained unlock must never silently complete a future session.
        if message.retain:
            return
        result = unlock_result(teams, message.topic, message.payload, callback, secret)
        if result is not None:
            team = message.topic.split('/')[1]
            client.publish(f'lab/{team}/result', result, qos=0, retain=False)

    client.on_connect = connected
    client.on_subscribe = subscribed
    client.on_disconnect = disconnected
    client.on_message = message
    client.connect_async(os.getenv('MQTT_HOST', 'mqtt'), 1883, 30)
    client.loop_forever(retry_first_connection=True)


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    main()
