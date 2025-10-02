import pprint
import requests


def tune():
    pprint.pprint(
        requests.post(
            "http://127.0.0.1:12345/tune",
            json=[
                "SELECT * FROM stadium;",
            ],
        ).json()
    )


def query():
    pprint.pprint(
        requests.post(
            "http://127.0.0.1:12345/query",
            json='SELECT * FROM stadium;',
        ).json()
    )


def knobs():
    pprint.pprint(
        requests.post(
            "http://127.0.0.1:12345/knobs",
        ).json()
    )


query()
knobs()
# tune()
