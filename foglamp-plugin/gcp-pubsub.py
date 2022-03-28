import io
import os
import json
import gzip
import numpy as np
import logging
from PIL import Image

from foglamp.common import logger
from google.cloud import pubsub_v1
from foglamp.common.common import _FOGLAMP_ROOT, _FOGLAMP_DATA


_LOGGER = logger.setup(__name__, level=logging.INFO)

_DEFAULT_CONFIG = {
    'plugin': {
         'description': 'Google Pub/Sub North Plugin',
         'type': 'string',
         'default': 'gcp-pubsub',
         'readonly': 'true'
    },
    'projectId': {
        'description': 'GCP cloud project name',
        'type': 'string',
        'default': 'decisive-light-339213',
        'order': '1',
        'displayName': 'Project ID',
        'mandatory': 'true'
    },
    'topic': {
        'description': 'A topic forwards messages from publishers to subscribers',
        'type': 'string',
        'default': 'camera-data',
        'order': '2',
        'displayName': 'Publish Topic',
        'mandatory': 'true'
    },
    'credentials': {
        'description': 'JSON key for the service account',
        'type': 'string',
        'default': 'credentials.json',
        'order': '3',
        'displayName': 'Credentials',
        'mandatory': 'true'
    },
    'source': {
        'description': 'Source of data to be sent on the stream. May be either readings or statistics',
        'type': 'enumeration',
        'default': 'readings',
        'options': ['readings', 'statistics'],
        'order': '4',
        'displayName': 'Source'
    },
    'outputFormat': {
        'description': 'Publish data in the format you want to be sent on the GCP. By default in PNG image format',
        'type': 'enumeration',
        'default': 'image',
        'options': ['image', 'bytes', 'JSON'],
        'order': '5',
        'displayName': 'Output Format'
    }
}


def plugin_info():
    return {
        'name': 'gcp-pubsub',
        'version': '1.9.2',
        'type': 'north',
        'interface': '1.0',
        'config': _DEFAULT_CONFIG
    }


def plugin_init(data):
    return data


def _get_certs_dir(_path):
    dir_path = _FOGLAMP_DATA + _path if _FOGLAMP_DATA else _FOGLAMP_ROOT + '/data' + _path
    if not os.path.exists(dir_path):
        os.makedirs(dir_path)
    certs_dir = os.path.expanduser(dir_path)
    return certs_dir


def _transmit_pubsub(pub, topic, data, op_format):
    _LOGGER.info("Transmitting data to Cloud Pub/Sub...")
    _LOGGER.debug("Type of Data: {} data: {} output pformat: {}".format(type(data), data, op_format))
    if op_format == 'bytes':
        compressed_data = gzip.compress(bytes(json.dumps(data), encoding="utf-8"))
        _LOGGER.debug("Compressed JSON data: {}".format(compressed_data))
        # Add other attributes like asset, id, ts, user_ts to message
        future = pub.publish(topic, compressed_data, asset=data['asset_code'], id=str(data['id']), ts=data['ts'],
                             user_ts=data['user_ts'])
    elif op_format == 'JSON':
        encoded_data = json.dumps(data).encode('utf-8')
        _LOGGER.debug("Send JSON in utf-8 encoded data: {}".format(encoded_data))
        # Add other attributes like asset, id, ts, user_ts to message
        future = pub.publish(topic, encoded_data)
        
        # asset=data['asset_code'], id=str(data['id']), ts=data['ts'], user_ts=data['user_ts'])
    elif op_format == 'image':
        new_reading = data
        key_to_remove = []
        for _dp in data['reading']:
            _LOGGER.debug("O/P format: {}-{}".format(op_format, _dp))
            if isinstance(data['reading'][_dp], np.ndarray):
                # Convert numpy array to PIL image
                pil_img = Image.fromarray(data['reading'][_dp], mode='L').convert('RGB')
                img_byte_arr = io.BytesIO()
                pil_img.save(img_byte_arr, format='PNG')
                img_content = img_byte_arr.getvalue()
                _LOGGER.debug("For datapoint: {} pil image content: {}".format(_dp, img_content))
                key_to_remove.append(_dp)
                # In case of image O/p with ndarray type we need to send each publish request
                # Add other attributes like asset, id, ts, user_ts to message
                future = pub.publish(topic, img_content, asset=data['asset_code'], id=str(data['id']), ts=data['ts'],
                                     user_ts=data['user_ts'])
            else:
                new_reading['reading'][_dp] = data['reading'][_dp]
        # numpy array keys needs to removed and send the full reading in compressed format
        for k in key_to_remove:
            del new_reading['reading'][k]
        _LOGGER.debug("New reading dict {}  in case of image format".format(new_reading))
        compressed_data = gzip.compress(bytes(json.dumps(new_reading), encoding="utf-8"))
        _LOGGER.debug("Compressed JSON data: {}".format(compressed_data))
        # Add other attributes like asset, id, ts, user_ts to message
        future = pub.publish(topic, compressed_data, asset=data['asset_code'], id=str(data['id']), ts=data['ts'],
                             user_ts=data['user_ts'])
    else:
        # TODO: more O/P format support in future
        user_encode_data = json.dumps(data).encode('utf-8')
        _LOGGER.debug("JSON data to bytes: {}".format(user_encode_data))
        future = pub.publish(topic, user_encode_data, asset=data['asset_code'], id=str(data['id']), ts=data['ts'],
                             user_ts=data['user_ts'])
    # When you publish a message, the client returns a future.
    _LOGGER.debug(future.result())
    _LOGGER.info("Published data: {} to Pub/Sub topic {}".format(data, topic))

    # If we want to see this publish data then use subscriber client
    # Either Google console - https://console.cloud.google.com/cloudpubsub/subscription/detail
    # Or write own subscriber client - http://googleapis.dev/python/pubsub/latest/index.html#subscribing

def convert_entry(entry):
    converted_entry = {}
    if 'user_ts' in entry:
        converted_entry['ts'] = entry['user_ts']
    if 'reading' in entry:
        if isinstance(entry['reading'], dict):
            for r_key in entry['reading'].keys():
                converted_entry[r_key] = entry['reading'][r_key]
        else:
            converted_entry['reading'] = entry['reading']
    return converted_entry


async def plugin_send(data, payload, stream_id):
    try:
        _LOGGER.debug("data with type: {}-{}".format(type(data), data))
        _LOGGER.debug("payload with type: {}-{}".format(type(payload), payload))
        _LOGGER.debug("stream_id with type: {}-{}".format(type(stream_id), stream_id))

        # Add JSON key for service account
        # This is a prerequisite and should be placed under $FLEDGE_DATA/etc/certs/json/<.json>
        json_certs_path = "{}/{}".format(_get_certs_dir('/etc/certs/json'), data['credentials']['value'])
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = json_certs_path

        # output format
        output_format = data['outputFormat']['value']

        # Publisher
        publisher = pubsub_v1.PublisherClient()
        # The `topic_path` method creates a fully qualified identifier
        # in the form `projects/{project_id}/topics/{topic_id}`
        topic_path = publisher.topic_path(data['projectId']['value'], data['topic']['value'])
        _LOGGER.debug("Publisher topic: {}".format(topic_path))
        full_reading = {}

        if output_format == 'JSON':
            converted_payload = {}
            for entry in payload:
                if entry['asset_code'] not in converted_payload:
                    converted_payload[entry['asset_code']] = []
                converted_payload[entry['asset_code']].append(convert_entry(entry))
            
            _transmit_pubsub(publisher, topic_path, converted_payload, output_format)
        else:
            for entry in payload:
                if 'reading' in payload[0]:
                    if isinstance(entry, dict):

                        for dp in entry['reading'].keys():

                            v = entry['reading'][dp]
                            full_reading[dp] = v
                            if isinstance(v, np.ndarray):

                                if output_format in ['bytes', 'JSON']:
                                    full_reading[dp] = v.tolist()
                        entry['reading'] = full_reading
                        _transmit_pubsub(publisher, topic_path, entry, output_format)
                    else:
                        _LOGGER.warning("**** 'reading' format should be in dict; Found:{}".format(
                            type(payload[0]['reading'])))
                else:
                    _LOGGER.warning("**** 'reading' key not present in payload[0]={}".format(payload[0]))
    except Exception as ex:
        _LOGGER.exception("Data could not be sent, {}".format(str(ex)))
    else:
        is_data_sent = True
        new_last_object_id = payload[-1]['id']
        num_sent = len(payload)
        _LOGGER.debug("data sent {} last object id {} num sent {}".format(is_data_sent, new_last_object_id, num_sent))
        return is_data_sent, new_last_object_id, num_sent


def plugin_shutdown(data):
    _LOGGER.debug('{} north plugin shut down'.format(_DEFAULT_CONFIG['plugin']['default']))


def plugin_reconfigure():
    pass
